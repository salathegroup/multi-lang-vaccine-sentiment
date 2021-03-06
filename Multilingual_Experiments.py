################################
####### IMPORT MODULES #########
################################
import sys, os, json, csv, datetime, pprint, uuid, time, argparse, logging

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s [%(levelname)-5.5s] [%(name)-12.12s]: %(message)s')
logger = logging.getLogger(__name__)

###################################
##### CLONING BERT AND THE DATA ###
###################################

# Clone Data
if not os.path.exists('data'):
    os.makedirs('data')
    os.system("gsutil -m cp -r gs://perepublic/EPFL_multilang/data/ .")
else:
    logger.info('** All training files has already been copied to data')

# Clone Bert
if not os.path.exists('bert_repo'):
    os.system(
        "test -d bert_repo || git clone https://github.com/google-research/bert bert_repo"
    )
else:
    logger.info('** The Bert repository has already been cloned')

if not 'bert_repo' in sys.path:
    sys.path += ['bert_repo']

###################################
##### IMPORT REMAINING MODULES ####
###################################
from vac_utils import performance_metrics, get_predictions_output, append_to_csv, save_to_json
import tensorflow as tf
import numpy as np
import modeling
import optimization
import run_classifier
import tokenization

##############################
########## CONSTANTS #########
##############################
BERT_MODEL_DIR = 'gs://perepublic/multi_cased_L-12_H-768_A-12/'
BERT_MODEL_NAME = 'bert_model.ckpt'
BERT_MODEL_FILE = os.path.join(BERT_MODEL_DIR, BERT_MODEL_NAME)
TEMP_OUTPUT_BASEDIR = 'gs://perepublic/finetuned_models/'
LOG_CSV_DIR = 'log_csv/'
PREDICTIONS_JSON_DIR = 'predictions_json/'
HIDDEN_STATE_JSON_DIR = 'hidden_state_json/'

logdirs = [LOG_CSV_DIR, PREDICTIONS_JSON_DIR, HIDDEN_STATE_JSON_DIR]

for d in logdirs:
    if not os.path.exists(d):
        os.makedirs(d)

##############################
####### HYPERPARAMETERS ######
##############################
LEARNING_RATE = 2e-5
MAX_SEQ_LENGTH = 128
# TRAIN_BATCH_SIZE = 64
TRAIN_BATCH_SIZE = 8
EVAL_BATCH_SIZE = 8
# PREDICT_BATCH_SIZE = 64
PREDICT_BATCH_SIZE = 8
WARMUP_PROPORTION = 0.1

##############################
############ CONFIG ##########
##############################
SAVE_CHECKPOINTS_STEPS = 1000
SAVE_SUMMARY_STEPS = 500

NUM_TPU_CORES = 8
# ITERATIONS_PER_LOOP = 1000
ITERATIONS_PER_LOOP = 10
LOWER_CASED = False

##############################
########### FUNCTIONS ########
##############################
def tpu_init(ip):
    #Set up the TPU
    from google.colab import auth
    auth.authenticate_user()
    tpu_address = 'grpc://' + str(ip) + ':8470'

    with tf.Session(tpu_address) as session:
        logger.info('TPU devices:')
        pprint.pprint(session.list_devices())
    logger.info(f'TPU address is active on {tpu_address}')
    return tpu_address


class vaccineStanceProcessor(run_classifier.DataProcessor):
    """Processor for the NoRec data set."""
    def get_train_examples(self, data_dir):
        """See base class."""
        return self._create_examples(
            self._read_tsv(os.path.join(data_dir, 'train.tsv')), 'train')

    def get_dev_examples(self, data_dir):
        """See base class."""
        return self._create_examples(
            self._read_tsv(os.path.join(data_dir, 'dev.tsv')), 'dev')

    def get_test_examples(self, data_dir):
        """See base class."""
        return self._create_examples(
            self._read_tsv(os.path.join(data_dir, 'test.tsv')), 'test')

    def get_labels(self):
        """See base class."""
        return ['positive', 'neutral', 'negative']

    def _create_examples(self, lines, set_type):
        """Creates examples for the training and dev sets."""
        examples = []
        for (i, line) in enumerate(lines):
            # Only the test set has a header
            if set_type == 'test' and i == 0:
                continue
            #guid = '%s-%s' % (set_type, i)
            guid = tokenization.convert_to_unicode(line[0])
            if set_type == 'test':
                text_a = tokenization.convert_to_unicode(line[3])
                #Set a dummy value. This is not used
                label = 'positive'
            else:
                text_a = tokenization.convert_to_unicode(line[3])
                label = tokenization.convert_to_unicode(line[1])
            examples.append(
                run_classifier.InputExample(guid=guid,
                                            text_a=text_a,
                                            text_b=None,
                                            label=label))
        return examples


##############################
##### DEFINE EXPERIMENTS #####
##############################

experiment_definitions = {
    "1": {
        "name": "zeroshot-cb-annot-en-cb-annot-en",
        "train_annot_dataset": "cb-annot-en",
        "eval_annot_dataset": "cb-annot-en"
    },
    "2": {
        "name": "zeroshot-cb-annot-en-cb-annot-de",
        "train_annot_dataset": "cb-annot-en",
        "eval_annot_dataset": "cb-annot-en-de"
    },
    "3": {
        "name": "zeroshot-cb-annot-en-cb-annot-es",
        "train_annot_dataset": "cb-annot-en",
        "eval_annot_dataset": "cb-annot-en-es"
    },
    "4": {
        "name": "zeroshot-cb-annot-en-cb-annot-fr",
        "train_annot_dataset": "cb-annot-en",
        "eval_annot_dataset": "cb-annot-en-fr"
    },
    "5": {
        "name": "zeroshot-cb-annot-en-cb-annot-pt",
        "train_annot_dataset": "cb-annot-en",
        "eval_annot_dataset": "cb-annot-en-pt"
    },
    "6": {
        "name": "translate-cb-annot-en-cb-annot-en",
        "train_annot_dataset": "cb-annot-en",
        "eval_annot_dataset": "cb-annot-en"
    },
    "7": {
        "name": "translate-cb-annot-de-cb-annot-de",
        "train_annot_dataset": "cb-annot-en-de",
        "eval_annot_dataset": "cb-annot-en-de"
    },
    "8": {
        "name": "translate-cb-annot-es-cb-annot-es",
        "train_annot_dataset": "cb-annot-en-es",
        "eval_annot_dataset": "cb-annot-en-es"
    },
    "9": {
        "name": "translate-cb-annot-fr-cb-annot-fr",
        "train_annot_dataset": "cb-annot-en-fr",
        "eval_annot_dataset": "cb-annot-en-fr"
    },
    "10": {
        "name": "translate-cb-annot-pt-cb-annot-pt",
        "train_annot_dataset": "cb-annot-en-pt",
        "eval_annot_dataset": "cb-annot-en-pt"
    },
    "11": {
        "name": "multitranslate-cb-annot-en-de-fr-es-pt-cb-annot-en",
        "train_annot_dataset": "cb-annot-en-de-fr-es-pt",
        "eval_annot_dataset": "cb-annot-en"
    },
    "12": {
        "name": "multitranslate-cb-annot-en-de-fr-es-pt-cb-annot-de",
        "train_annot_dataset": "cb-annot-en-de-fr-es-pt",
        "eval_annot_dataset": "cb-annot-en-de"
    },
    "13": {
        "name": "multitranslate-cb-annot-en-de-fr-es-pt-cb-annot-es",
        "train_annot_dataset": "cb-annot-en-de-fr-es-pt",
        "eval_annot_dataset": "cb-annot-en-es"
    },
    "14": {
        "name": "multitranslate-cb-annot-en-de-fr-es-pt-cb-annot-fr",
        "train_annot_dataset": "cb-annot-en-de-fr-es-pt",
        "eval_annot_dataset": "cb-annot-en-fr"
    },
    "15": {
        "name": "multitranslate-cb-annot-en-de-fr-es-pt-cb-annot-pt",
        "train_annot_dataset": "cb-annot-en-de-fr-es-pt",
        "eval_annot_dataset": "cb-annot-en-pt"
    },
    "16": {
        "name": "zeroshot-small-cb-annot-en-sm-cb-annot-en",
        "train_annot_dataset": "cb-annot-en-sm",
        "eval_annot_dataset": "cb-annot-en"
    },
    "17": {
        "name": "zeroshot-small-cb-annot-en-sm-cb-annot-de",
        "train_annot_dataset": "cb-annot-en-sm",
        "eval_annot_dataset": "cb-annot-en-de"
    },
    "18": {
        "name": "zeroshot-small-cb-annot-en-sm-cb-annot-es",
        "train_annot_dataset": "cb-annot-en-sm",
        "eval_annot_dataset": "cb-annot-en-es"
    },
    "19": {
        "name": "zeroshot-small-cb-annot-en-sm-cb-annot-fr",
        "train_annot_dataset": "cb-annot-en-sm",
        "eval_annot_dataset": "cb-annot-en-fr"
    },
    "20": {
        "name": "zeroshot-small-cb-annot-en-sm-cb-annot-pt",
        "train_annot_dataset": "cb-annot-en-sm",
        "eval_annot_dataset": "cb-annot-en-pt"
    },
    "21": {
        "name": "translate-small-cb-annot-en-sm-cb-annot-en",
        "train_annot_dataset": "cb-annot-en-sm",
        "eval_annot_dataset": "cb-annot-en"
    },
    "22": {
        "name": "translate-small-cb-annot-de-sm-cb-annot-de",
        "train_annot_dataset": "cb-annot-en-de-sm",
        "eval_annot_dataset": "cb-annot-en-de"
    },
    "23": {
        "name": "translate-small-cb-annot-es-sm-cb-annot-es",
        "train_annot_dataset": "cb-annot-en-es-sm",
        "eval_annot_dataset": "cb-annot-en-es"
    },
    "24": {
        "name": "translate-small-cb-annot-fr-sm-cb-annot-fr",
        "train_annot_dataset": "cb-annot-en-fr-sm",
        "eval_annot_dataset": "cb-annot-en-fr"
    },
    "25": {
        "name": "translate-small-cb-annot-pt-sm-cb-annot-pt",
        "train_annot_dataset": "cb-annot-en-pt-sm",
        "eval_annot_dataset": "cb-annot-en-pt"
    },
    "26": {
        "name": "multitranslate-small-cb-annot-en-de-fr-es-pt-sm-cb-annot-en",
        "train_annot_dataset": "cb-annot-en-de-fr-es-pt-sm",
        "eval_annot_dataset": "cb-annot-en"
    },
    "27": {
        "name": "multitranslate-small-cb-annot-en-de-fr-es-pt-sm-cb-annot-de",
        "train_annot_dataset": "cb-annot-en-de-fr-es-pt-sm",
        "eval_annot_dataset": "cb-annot-en-de"
    },
    "28": {
        "name": "multitranslate-small-cb-annot-en-de-fr-es-pt-sm-cb-annot-es",
        "train_annot_dataset": "cb-annot-en-de-fr-es-pt-sm",
        "eval_annot_dataset": "cb-annot-en-es"
    },
    "29": {
        "name": "multitranslate-small-cb-annot-en-de-fr-es-pt-sm-cb-annot-fr",
        "train_annot_dataset": "cb-annot-en-de-fr-es-pt-sm",
        "eval_annot_dataset": "cb-annot-en-fr"
    },
    "30": {
        "name": "multitranslate-small-cb-annot-en-de-fr-es-pt-sm-cb-annot-pt",
        "train_annot_dataset": "cb-annot-en-de-fr-es-pt-sm",
        "eval_annot_dataset": "cb-annot-en-pt"
    },
    "31": {
        "name": "balanced-cb-annot-en-de-fr-es-pt-os-cb-annot-en",
        "train_annot_dataset": "cb-annot-en-de-fr-es-pt-os",
        "eval_annot_dataset": "cb-annot-en"
    },
    "32": {
        "name": "balanced-cb-annot-en-de-fr-es-pt-os-cb-annot-de",
        "train_annot_dataset": "cb-annot-en-de-fr-es-pt-os",
        "eval_annot_dataset": "cb-annot-en-de"
    },
    "33": {
        "name": "balanced-cb-annot-en-de-fr-es-pt-os-cb-annot-es",
        "train_annot_dataset": "cb-annot-en-de-fr-es-pt-os",
        "eval_annot_dataset": "cb-annot-en-es"
    },
    "34": {
        "name": "balanced-cb-annot-en-de-fr-es-pt-os-cb-annot-fr",
        "train_annot_dataset": "cb-annot-en-de-fr-es-pt-os",
        "eval_annot_dataset": "cb-annot-en-fr"
    },
    "35": {
        "name": "balanced-cb-annot-en-de-fr-es-pt-os-cb-annot-pt",
        "train_annot_dataset": "cb-annot-en-de-fr-es-pt-os",
        "eval_annot_dataset": "cb-annot-en-pt"
    },
    "36": {
        "name": "balanced-cb-annot-en-de-fr-es-pt-us-cb-annot-en",
        "train_annot_dataset": "cb-annot-en-de-fr-es-pt-us",
        "eval_annot_dataset": "cb-annot-en"
    },
    "37": {
        "name": "balanced-cb-annot-en-de-fr-es-pt-us-cb-annot-de",
        "train_annot_dataset": "cb-annot-en-de-fr-es-pt-us",
        "eval_annot_dataset": "cb-annot-en-de"
    },
    "38": {
        "name": "balanced-cb-annot-en-de-fr-es-pt-us-cb-annot-es",
        "train_annot_dataset": "cb-annot-en-de-fr-es-pt-us",
        "eval_annot_dataset": "cb-annot-en-es"
    },
    "39": {
        "name": "balanced-cb-annot-en-de-fr-es-pt-us-cb-annot-fr",
        "train_annot_dataset": "cb-annot-en-de-fr-es-pt-us",
        "eval_annot_dataset": "cb-annot-en-fr"
    },
    "40": {
        "name": "balanced-cb-annot-en-de-fr-es-pt-us-cb-annot-pt",
        "train_annot_dataset": "cb-annot-en-de-fr-es-pt-us",
        "eval_annot_dataset": "cb-annot-en-pt"
    }
}

###########################
##### RUN EXPERIMENTS #####
###########################


def run_experiment(experiments, use_tpu, tpu_address, repeat, num_train_steps, username, comment, store_last_layer):
    logger.info(f'Getting ready to run the following experiments for {repeat} repeats: {experiments}')

    def get_run_config(output_dir):
        return tf.contrib.tpu.RunConfig(
            cluster=tpu_cluster_resolver,
            model_dir=output_dir,
            save_checkpoints_steps=SAVE_CHECKPOINTS_STEPS,
            tpu_config=tf.contrib.tpu.TPUConfig(
                iterations_per_loop=ITERATIONS_PER_LOOP,
                num_shards=NUM_TPU_CORES,
                per_host_input_for_training=tf.contrib.tpu.InputPipelineConfig.
                PER_HOST_V2))

    def parse_experiments_argument(experiments):
        """Returns list of experiments from comma-separated string as list"""
        exp_list = []
        for part in experiments.split(','):
            if '-' in part:
                a, b = part.split('-')
                a, b = int(a), int(b)
                exp_list.extend(range(a, b + 1))
            else:
                exp_list.append(part)
        exp_list = [str(s) for s in exp_list]
        return exp_list

    experiments = parse_experiments_argument(experiments)
    last_completed_train = ""
    completed_train_dirs = []

    for exp_nr in experiments:
        logger.info(f"***** Starting Experiment {exp_nr} *******")
        logger.info(f"***** {experiment_definitions[exp_nr]['name']} ******")
        logger.info("***********************************************")

        #Get a unique ID for every experiment run
        experiment_id = str(uuid.uuid4())

        ###########################
        ######### TRAINING ########
        ###########################

        #We should only train a new model if a similar model hasnt just been trained. Save considerable computation time
        train_annot_dataset = experiment_definitions[exp_nr][
            "train_annot_dataset"]


        if train_annot_dataset != last_completed_train:
            #Set a fresh new output directory every time training starts, and set the cache to this directory
            temp_output_dir = os.path.join(
                TEMP_OUTPUT_BASEDIR,experiment_id)

            os.environ['TFHUB_CACHE_DIR'] = temp_output_dir
            logger.info(f"***** Setting temporary dir {temp_output_dir} **")
            logger.info(f"***** Train started in {temp_output_dir} **")

            tokenizer = tokenization.FullTokenizer(vocab_file=os.path.join(
                BERT_MODEL_DIR, 'vocab.txt'),
                                                   do_lower_case=LOWER_CASED)


            if tpu_address:
                tpu_cluster_resolver = tf.contrib.cluster_resolver.TPUClusterResolver(tpu_address)
            else:
                tpu_cluster_resolver = None

            processor = vaccineStanceProcessor()
            label_list = processor.get_labels()
            label_mapping = dict(zip(range(len(label_list)), label_list))

            train_examples = processor.get_train_examples(
                os.path.join('data', train_annot_dataset))
            num_warmup_steps = int(num_train_steps * WARMUP_PROPORTION)

            #Initiation

            bert_config = modeling.BertConfig.from_json_file(os.path.join(BERT_MODEL_DIR, 'bert_config.json'))
            model_fn = model_fn_builder(
                bert_config=bert_config,
                num_labels=len(label_list),
                init_checkpoint=BERT_MODEL_FILE,
                learning_rate=LEARNING_RATE,
                num_train_steps=num_train_steps,
                num_warmup_steps=num_warmup_steps,
                use_tpu=use_tpu,
                use_one_hot_embeddings=True,
                extract_last_layer=store_last_layer
                )

            estimator = tf.contrib.tpu.TPUEstimator(
                use_tpu=use_tpu,
                model_fn=model_fn,
                config=get_run_config(temp_output_dir),
                train_batch_size=TRAIN_BATCH_SIZE,
                eval_batch_size=EVAL_BATCH_SIZE,
                predict_batch_size=PREDICT_BATCH_SIZE,
            )

            train_features = run_classifier.convert_examples_to_features(
                train_examples, label_list, MAX_SEQ_LENGTH, tokenizer)

            logger.info('***** Fine tuning BERT base model normally takes a few minutes. Please wait...')
            logger.info('***** Started training using {} at {} *****'.format(train_annot_dataset, datetime.datetime.now()))
            logger.info('  Num examples = {}'.format(len(train_examples)))
            logger.info('  Batch size = {}'.format(TRAIN_BATCH_SIZE))
            logger.info('  Train steps = {}'.format(num_train_steps))
            logger.info('  Number of training steps = {}'.format(num_train_steps))

            tf.logging.info('  Num steps = %d', num_train_steps)
            train_input_fn = run_classifier.input_fn_builder(
                features=train_features,
                seq_length=MAX_SEQ_LENGTH,
                is_training=True,
                drop_remainder=True)

            estimator.train(input_fn=train_input_fn, max_steps=num_train_steps)
            logger.info('***** Finished training using {} at {} *****'.format(train_annot_dataset, datetime.datetime.now()))

            last_completed_train = train_annot_dataset
            completed_train_dirs.append(temp_output_dir)

            ######################################
            ######### TRAINING PREDICTION ########
            ######################################
            train_pred_input_fn = run_classifier.input_fn_builder(
                features=train_features,
                seq_length=MAX_SEQ_LENGTH,
                is_training=False,
                drop_remainder=False)

            predictions = estimator.predict(input_fn=train_pred_input_fn)
            probabilities, last_layer = list(zip(*[[p['probabilities'], p['last_layer']] for p in predictions]))
            probabilities = np.array(probabilities)
            if store_last_layer:
                # extract state for CLS token 
                last_layer = [_l[0] for _l in last_layer]
            else:
                last_layer = None
            y_true = [e.label_id for e in train_features]
            guid = [e.guid for e in train_examples]
            predictions_output = get_predictions_output(experiment_id, guid, probabilities, y_true, cls_hidden_state=last_layer, label_mapping=label_mapping, dataset='train')
            save_to_json(predictions_output ,os.path.join(PREDICTIONS_JSON_DIR, f'train_{experiment_id}.json'))

        #############################
        ######### EVALUATING ########
        #############################
        eval_annot_dataset = experiment_definitions[exp_nr][
            "eval_annot_dataset"]

        eval_examples = processor.get_dev_examples(
            os.path.join('data', eval_annot_dataset))
        eval_features = run_classifier.convert_examples_to_features(
            eval_examples, label_list, MAX_SEQ_LENGTH, tokenizer)
        logger.info('***** Started evaluation of {} at {} *****'.format(
            experiment_definitions[exp_nr]["name"], datetime.datetime.now()))
        logger.info('Num examples = {}'.format(len(eval_examples)))
        logger.info('Batch size = {}'.format(EVAL_BATCH_SIZE))

        # Eval will be slightly WRONG on the TPU because it will truncate the last batch.
        eval_steps = int(len(eval_examples) / EVAL_BATCH_SIZE)
        eval_input_fn = run_classifier.input_fn_builder(
            features=eval_features,
            seq_length=MAX_SEQ_LENGTH,
            is_training=False,
            drop_remainder=True)
        result = estimator.evaluate(input_fn=eval_input_fn, steps=eval_steps)

        logger.info(
            '***** Finished first half of evaluation of {} at {} *****'.format(
                experiment_definitions[exp_nr]["name"],
                datetime.datetime.now()))

        output_eval_file = os.path.join(temp_output_dir, 'eval_results.txt')
        with tf.gfile.GFile(output_eval_file, 'w') as writer:
            logger.info('***** Eval results *****')
            for key in sorted(result.keys()):
                logger.info('  {} = {}'.format(key, str(result[key])))
                writer.write('%s = %s\n' % (key, str(result[key])))

        predictions = estimator.predict(eval_input_fn)
        probabilities = np.array([p['probabilities'] for p in predictions])
        y_pred = np.argmax(probabilities, axis=1)
        y_true = [e.label_id for e in eval_features]
        guid = [e.guid for e in eval_examples]
        scores = performance_metrics(y_true,
                                     y_pred,
                                     label_mapping=label_mapping)
        logger.info('Final scores:')
        logger.info(scores)
        logger.info('***** Finished second half of evaluation of {} at {} *****'.
              format(experiment_definitions[exp_nr]["name"],
                     datetime.datetime.now()))

        # write full dev prediction output
        predictions_output = get_predictions_output(experiment_id, guid, probabilities, y_true, label_mapping=label_mapping, dataset='dev')
        save_to_json(predictions_output, os.path.join(PREDICTIONS_JSON_DIR, f'dev_{experiment_id}.json'))

        # Write log to Training Log File
        data = {
            'Experiment_Name': experiment_definitions[exp_nr]["name"],
            'Experiment_Id':experiment_id,
            'Date': format(datetime.datetime.now()),
            'User': username,
            'Model': BERT_MODEL_NAME,
            'Num_Train_Steps': num_train_steps,
            'Train_Annot_Dataset': train_annot_dataset,
            'Eval_Annot_Dataset': eval_annot_dataset,
            'Learning_Rate': LEARNING_RATE,
            'Max_Seq_Length': MAX_SEQ_LENGTH,
            'Eval_Loss': result['eval_loss'],
            'Loss': result['loss'],
            'Comment': comment,
            **scores
        }

        append_to_csv(data, os.path.join(LOG_CSV_DIR,'fulltrainlog.csv'))
        logger.info(f"***** Completed Experiment {exp_nr} *******")

    logger.info(f"***** Completed all experiments in {repeat} repeats. We should now clean up all remaining files *****")
    for c in completed_train_dirs:
        logger.info("Deleting these directories: ")
        logger.info("gsutil -m rm -r " + c)
        os.system("gsutil -m rm -r " + c)

def model_fn_builder(bert_config, num_labels, init_checkpoint, learning_rate, num_train_steps, num_warmup_steps, use_tpu, use_one_hot_embeddings, extract_last_layer=False):
    """Returns `model_fn` closure for TPUEstimator."""
    def model_fn(features, labels, mode, params):
        """The `model_fn` for TPUEstimator."""
        tf.logging.info("*** Features ***")
        for name in sorted(features.keys()):
            tf.logging.info("  name = %s, shape = %s" % (name, features[name].shape))
        input_ids = features["input_ids"]
        input_mask = features["input_mask"]
        segment_ids = features["segment_ids"]
        label_ids = features["label_ids"]
        is_real_example = None
        if "is_real_example" in features:
            is_real_example = tf.cast(features["is_real_example"], dtype=tf.float32)
        else:
            is_real_example = tf.ones(tf.shape(label_ids), dtype=tf.float32)
        is_training = (mode == tf.estimator.ModeKeys.TRAIN)
        model, (total_loss, per_example_loss, logits, probabilities) = create_model(
                bert_config, is_training, input_ids, input_mask, segment_ids, label_ids,
                num_labels, use_one_hot_embeddings)
        tvars = tf.trainable_variables()
        initialized_variable_names = {}
        scaffold_fn = None
        if init_checkpoint:
            (assignment_map, initialized_variable_names
            ) = modeling.get_assignment_map_from_checkpoint(tvars, init_checkpoint)
            if use_tpu:
                def tpu_scaffold():
                    tf.train.init_from_checkpoint(init_checkpoint, assignment_map)
                    return tf.train.Scaffold()
                scaffold_fn = tpu_scaffold
            else:
                tf.train.init_from_checkpoint(init_checkpoint, assignment_map)
        tf.logging.info("**** Trainable Variables ****")
        for var in tvars:
            init_string = ""
            if var.name in initialized_variable_names:
                init_string = ", *INIT_FROM_CKPT*"
            tf.logging.info("  name = %s, shape = %s%s", var.name, var.shape,
                                            init_string)
        output_spec = None
        if mode == tf.estimator.ModeKeys.TRAIN:
            train_op = optimization.create_optimizer(
                    total_loss, learning_rate, num_train_steps, num_warmup_steps, use_tpu)
            output_spec = tf.contrib.tpu.TPUEstimatorSpec(
                    mode=mode,
                    loss=total_loss,
                    train_op=train_op,
                    scaffold_fn=scaffold_fn)
        elif mode == tf.estimator.ModeKeys.EVAL:
            def metric_fn(per_example_loss, label_ids, logits, is_real_example):
                predictions = tf.argmax(logits, axis=-1, output_type=tf.int32)
                accuracy = tf.metrics.accuracy(
                        labels=label_ids, predictions=predictions, weights=is_real_example)
                loss = tf.metrics.mean(values=per_example_loss, weights=is_real_example)
                return {"eval_accuracy": accuracy, "eval_loss": loss}
            eval_metrics = (metric_fn, [per_example_loss, label_ids, logits, is_real_example])
            output_spec = tf.contrib.tpu.TPUEstimatorSpec(
                    mode=mode,
                    loss=total_loss,
                    eval_metrics=eval_metrics,
                    scaffold_fn=scaffold_fn)
        else:
            last_layer = None
            if extract_last_layer:
                last_layer = model.get_all_encoder_layers()[-1]
            output_spec = tf.contrib.tpu.TPUEstimatorSpec(
                    mode=mode,
                    predictions={"probabilities": probabilities, 'last_layer': last_layer},
                    scaffold_fn=scaffold_fn)
        return output_spec
    return model_fn


def create_model(bert_config, is_training, input_ids, input_mask, segment_ids, labels, num_labels, use_one_hot_embeddings):
    """Creates a classification model."""
    model = modeling.BertModel(
            config=bert_config,
            is_training=is_training,
            input_ids=input_ids,
            input_mask=input_mask,
            token_type_ids=segment_ids,
            use_one_hot_embeddings=use_one_hot_embeddings)
    output_layer = model.get_pooled_output()
    hidden_size = output_layer.shape[-1].value
    output_weights = tf.get_variable(
            "output_weights", [num_labels, hidden_size],
            initializer=tf.truncated_normal_initializer(stddev=0.02))
    output_bias = tf.get_variable(
            "output_bias", [num_labels], initializer=tf.zeros_initializer())
    with tf.variable_scope("loss"):
        if is_training:
            # I.e., 0.1 dropout
            output_layer = tf.nn.dropout(output_layer, keep_prob=0.9)
        logits = tf.matmul(output_layer, output_weights, transpose_b=True)
        logits = tf.nn.bias_add(logits, output_bias)
        probabilities = tf.nn.softmax(logits, axis=-1)
        log_probs = tf.nn.log_softmax(logits, axis=-1)
        one_hot_labels = tf.one_hot(labels, depth=num_labels, dtype=tf.float32)
        per_example_loss = -tf.reduce_sum(one_hot_labels * log_probs, axis=-1)
        loss = tf.reduce_mean(per_example_loss)
    return model, (loss, per_example_loss, logits, probabilities)


def parse_args(args):
    # Parse commandline
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--tpu_ip',
        dest='tpu_ip',
        default=None,
        help='IP-address of the TPU')
    parser.add_argument(
        '--use_tpu',
        dest='use_tpu',
        action='store_true',
        default=False,
        help='Use TPU. Set to 1 or 0. If set to false, GPU will be used instead')
    parser.add_argument(
        '-u',
        '--username',
        help='Optional. Username is used in the directory name and in the logfile',
        default='Anonymous')
    parser.add_argument(
        '-r',
        '--repeats',
        help='Number of times the script should run. Default is 1',
        default=1,
        type=int)
    parser.add_argument(
        '-e',
        '--experiments',
        type=str,
        help='Experiment numbers to run. Use , to separate individual runs or - to run a sequence of runs.',
        default='1')
    parser.add_argument(
        '-n',
        '--num_train_steps',
        help='Number of train steps. Default is 100',
        default=100,
        type=int)
    parser.add_argument(
        '--store_last_layer',
        action='store_true',
        default=False,
        help='Store last layer of encoder')
    parser.add_argument(
        '--comment',
        help='Optional. Add a Comment to the logfile for internal reference.',
        default='No Comment')
    args = parser.parse_args()
    return args

def main(args):
    args = parse_args(args)

    #Initialise the TPUs if they are used
    if args.use_tpu == 1:
        use_tpu = True
        tpu_address = tpu_init(args.tpu_ip)
        logger.info('Using TPU')
    else:
        use_tpu = False
        tpu_address = None
        logger.info('Using GPU')

    for repeat in range(args.repeats):
        run_experiment(args.experiments, use_tpu, tpu_address, repeat+1, args.num_train_steps,
                       args.username, args.comment, args.store_last_layer)
        logger.info(f'*** Completed repeats {repeat + 1}')


if __name__ == "__main__":
    main(sys.argv[1:])
