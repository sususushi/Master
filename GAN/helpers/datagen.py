import numpy as np
from keras.preprocessing.text import Tokenizer

from GAN.helpers.enums import NoiseMode, Conf, WordEmbedding, PreInit
from GAN.helpers.list_helpers import pairwise_cosine_similarity
from helpers.io_helper import load_pickle_file
from helpers.list_helpers import print_progress
from word2vec.word2vec_helpers import get_dict_filename


def to_categorical_lists(captions, word_to_id_dict, config):
	matrix = np.zeros((len(captions), config[Conf.MAX_SEQ_LENGTH], config[Conf.VOCAB_SIZE]))
	for caption_index in range(len(captions)):
		caption = captions[caption_index]
		for word_index in range(config[Conf.MAX_SEQ_LENGTH]):
			if word_index >= len(caption):
				word = word_to_id_dict['<pad>']
			else:
				word = caption[word_index]
			matrix[caption_index, word_index, word] = 1.
	return matrix


def onehot_to_softmax(one_hot, max_range=(0.5, 1.0), min_range=(0.0, 0.001)):
	softmax = np.random.uniform(min_range[0], min_range[1], one_hot.shape).astype(dtype="float32")
	for i, one_hot_sentence in enumerate(one_hot):
		for j, one_hot_word in enumerate(one_hot_sentence):
			new_word = softmax[i][j]
			new_word[np.argmax(one_hot_word)] = np.random.uniform(max_range[0], max_range[1])
			word_sum = new_word.sum()
			softmax[i][j] = new_word / word_sum
	return softmax


def generate_index_sentences(config, cap_data=-1):
	max_seq_length = config[Conf.MAX_SEQ_LENGTH]
	nb_words = config[Conf.VOCAB_SIZE]

	if config[Conf.LIMITED_DATASET] is not None:
		print "Loading %s sentences" % config[Conf.LIMITED_DATASET]
		word_captions = get_custom_sentences(config)
	else:
		word_captions = get_flickr_sentences(cap_data)
	word_captions = ['<sos> ' + line + ' <eos> <pad>' for line in word_captions]

	tokenizer = Tokenizer(nb_words=nb_words, filters="""!"#$%&'()*+-/:;=?@[\]^_`{|}~""")
	tokenizer.fit_on_texts(word_captions)

	word_to_id_dict = tokenizer.word_index
	id_to_word_dict = {token: idx for idx, token in word_to_id_dict.items()}

	index_captions = tokenizer.texts_to_sequences(word_captions)
	# index_captions = [cap for cap in index_captions if len(cap) <= max_seq_length]
	return index_captions, id_to_word_dict, word_to_id_dict


def generate_string_sentences(config):
	cap_data = config[Conf.DATASET_SIZE]
	if config[Conf.LIMITED_DATASET] is not None:
		print "Loading %s sentences" % config[Conf.LIMITED_DATASET]
		sentences = get_custom_sentences(config)
	else:
		print "Loading Flickr sentences..."
		sentences = get_flickr_sentences(cap_data)
	return preprocess_sentences(config, sentences)


def preprocess_sentences(config, sentences):
	sos_token = "<sos>"
	eos_token = "<eos>"
	pad_token = "<pad>"
	if config[Conf.WORD_EMBEDDING] == WordEmbedding.GLOVE:
		print "Loading Glove dictionary..."
		word_embedding_dict = get_word_embeddings()
		sos_token = "<"
		eos_token = ">"
		pad_token = "="
	else:
		filename = get_dict_filename(config[Conf.EMBEDDING_SIZE], config[Conf.WORD2VEC_NUM_STEPS],
		                             config[Conf.VOCAB_SIZE], config[Conf.W2V_SET])
		print "Loading Word2Vec dictionary (%s)..." % filename
		# word_embedding_dict = load_pickle_file("word2vec/saved_models/word2vec_%sd%svoc%ssteps_dict.pkl" % (config[Conf.EMBEDDING_SIZE], config[Conf.VOCAB_SIZE], config[Conf.WORD2VEC_NUM_STEPS]))
		word_embedding_dict = load_pickle_file(filename)

	word_list_sentences = []
	for sentence in sentences:
		word_list = [sos_token]
		for word in sentence.split(" "):
			word_list.append(word.lower())
		word_list.append(eos_token)
		while len(word_list) < config[Conf.MAX_SEQ_LENGTH]:
			word_list.append(pad_token)
		word_list_sentences.append(word_list)
	# word_list_sentences = [[word.lower() for word in sentence.split(" ")] for sentence in sentences]
	return np.asarray(word_list_sentences), word_embedding_dict


def get_flickr_sentences(cap_data):
	path = "data/datasets/Flickr8k.txt"

	sentence_file = open(path)
	if cap_data == -1:
		word_captions = sentence_file.readlines()
	else:
		word_captions = sentence_file.readlines()[:cap_data]
	sentence_file.close()
	word_captions = [(line.split("\t")[1]).strip() for line in word_captions]
	return word_captions


def get_custom_sentences(config):
	if config[Conf.LIMITED_DATASET].endswith(".txt"):
		path = "data/datasets/%s" % config[Conf.LIMITED_DATASET]
		sentence_file = open(path)
		word_captions = sentence_file.readlines()
		sentence_file.close()
		word_captions = [line.strip() for line in word_captions]
	else:
		word_captions = fetch_flower_captions(config)

	return word_captions

import random
def generate_input_noise(config):
	if config[Conf.PREINIT] == PreInit.ENCODER_DECODER:
		if config[Conf.WORD_EMBEDDING] == WordEmbedding.ONE_HOT:
			noise_size = config[Conf.VOCAB_SIZE]
		else:
			noise_size = config[Conf.EMBEDDING_SIZE]
	else:
		noise_size = config[Conf.NOISE_SIZE]

	if config[Conf.NOISE_MODE] == NoiseMode.REPEAT:
		noise_matrix = np.zeros((config[Conf.BATCH_SIZE], config[Conf.MAX_SEQ_LENGTH], noise_size))
		for batch_index in range(config[Conf.BATCH_SIZE]):
			word_noise = np.random.normal(size=noise_size)
			for word_index in range(config[Conf.MAX_SEQ_LENGTH]):
				noise_matrix[batch_index][word_index] = word_noise

		return noise_matrix

	elif config[Conf.NOISE_MODE] == NoiseMode.REPEAT_SINGLE:
		noise_matrix = np.zeros((config[Conf.BATCH_SIZE], noise_size))
		for batch_index in range(config[Conf.BATCH_SIZE]):
			noise_matrix[batch_index] = np.random.normal(size=noise_size)

		return noise_matrix

	elif config[Conf.NOISE_MODE] == NoiseMode.NEW:
		return np.random.rand(config[Conf.BATCH_SIZE], config[Conf.MAX_SEQ_LENGTH], noise_size)

	elif config[Conf.NOISE_MODE] == NoiseMode.FIRST_ONLY:
		noise_matrix = np.zeros((config[Conf.BATCH_SIZE], config[Conf.MAX_SEQ_LENGTH], noise_size))
		for batch_index in range(config[Conf.BATCH_SIZE]):
			word_noise = np.random.normal(size=noise_size)
			for word_index in range(config[Conf.MAX_SEQ_LENGTH]):
				noise_matrix[batch_index][word_index] = word_noise
		for batch_index in range(config[Conf.BATCH_SIZE]):
			if random.random() < 0.5:
				word_noise = np.zeros(noise_size)
			else:
				word_noise = np.ones(noise_size)
			noise_matrix[batch_index][0] = word_noise
		return noise_matrix

	elif config[Conf.NOISE_MODE] == NoiseMode.ONES:
		return np.ones((config[Conf.BATCH_SIZE], config[Conf.MAX_SEQ_LENGTH], noise_size))

	elif config[Conf.NOISE_MODE] == NoiseMode.ENCODING:
		embedded_data = load_pickle_file(
			"sequence_to_sequence/logs/S2S_2EMB_2017-04-04_VS2+1000_BS128_HD30_DHL1_ED50_SEQ5_WEMword2vec/encoded_data.pkl")
		random_distribution_of_embedded_data = []
		for i in range(config[Conf.BATCH_SIZE]):
			# random_distribution_of_embedded_data.append(embedded_data[np.random.randint(0, len(embedded_data))])
			random_distribution_of_embedded_data.append(embedded_data[i])
		return np.asarray(random_distribution_of_embedded_data)


def get_word_embeddings():
	embeddings_index = {}
	f = open('data/datasets/glove.6B.50d.txt')
	count = 0
	for line in f:
		values = line.split()
		word = values[0]
		coefs = np.asarray(values[1:], dtype='float32')
		embeddings_index[word] = coefs
		count += 1
		if count % 100 == 0:
			print_progress(count, 400000, prefix="Producing glove word embeddings")
	f.close()
	return embeddings_index


def emb_generate_caption_training_batch(training_batch, word_embedding_dict, config):
	embedding_lists = []
	for word_list in training_batch:
		embedding_sentence = []
		for word_string in word_list:
			if word_string in word_embedding_dict:
				word_embedding = word_embedding_dict[word_string]
				embedding_sentence.append(word_embedding)
		if len(embedding_sentence) > config[Conf.MAX_SEQ_LENGTH]:
			embedding_sentence = embedding_sentence[:config[Conf.MAX_SEQ_LENGTH]]
		while len(embedding_sentence) < config[Conf.MAX_SEQ_LENGTH]:
			if config[Conf.WORD_EMBEDDING] == WordEmbedding.GLOVE:
				embedding_sentence.append(word_embedding_dict["="])
			else:
				embedding_sentence.append(word_embedding_dict["<pad>"])
		embedding_lists.append(embedding_sentence)
	return np.asarray(embedding_lists)


def generate_image_training_batch(image_batch, config):
	image_batch = [[x] for x in image_batch]
	return np.repeat(image_batch, config[Conf.MAX_SEQ_LENGTH], axis=1)


def generate_image_with_noise_training_batch(image_batch, config):
	noise = generate_input_noise(config)
	for batch_index in range(len(image_batch)):
		for i in range(int(config[Conf.MAX_SEQ_LENGTH] * 0.5)):
			noise[batch_index][i] = image_batch[batch_index]
	return noise
