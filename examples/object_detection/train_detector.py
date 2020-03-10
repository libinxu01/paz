import os
import argparse
from tensorflow.keras.optimizers import SGD
from tensorflow.keras.callbacks import CSVLogger, ModelCheckpoint
from paz.optimization.callbacks import LearningRateScheduler
from paz.pipelines import DetectionAugmentation
from paz.models import SSD300
from paz.datasets import VOC
from paz.optimization import MultiBoxLoss
from paz.core.sequencer import ProcessingSequencer
from paz.optimization.callbacks import EvaluateMAP
from paz.pipelines import SingleShotInference

description = 'Training script for single-shot object detection models'
parser = argparse.ArgumentParser(description=description)
parser.add_argument('-bs', '--batch_size', default=32, type=int,
                    help='Batch size for training')
parser.add_argument('-st', '--steps_per_epoch', default=1000, type=int,
                    help='Batch size for training')
parser.add_argument('-et', '--eval_per_epoch', default=10, type=int,
                    help='evaluation frequency')
parser.add_argument('-lr', '--learning_rate', default=0.001, type=float,
                    help='Initial learning rate for SGD')
parser.add_argument('-m', '--momentum', default=0.9, type=float,
                    help='Momentum for SGD')
parser.add_argument('-g', '--gamma_decay', default=0.1, type=float,
                    help='Gamma decay for learning rate scheduler')
parser.add_argument('-e', '--num_epochs', default=120, type=int,
                    help='Maximum number of epochs before finishing')
parser.add_argument('-sp', '--save_path', default='trained_models/',
                    type=str, help='Path for writing model weights and logs')
parser.add_argument('-dp', '--data_path', default='/home/username/Vocdevkit/',
                    type=str, help='Path for writing model weights and logs')
parser.add_argument('-se', '--scheduled_epochs', nargs='+', type=int,
                    default=[55, 76],
                    help='Kernels used in each block e.g. 128 256 512')
args = parser.parse_args()

optimizer = SGD(args.learning_rate, args.momentum)

data_splits = [['trainval', 'trainval'], 'test']
data_names = [['VOC2007', 'VOC2012'], 'VOC2007']

# loading datasets
data_managers, datasets, eval_datasets = [], [], []
for data_name, data_split in zip(data_names, data_splits):
    data_manager = VOC(args.data_path, data_split, name=data_name)
    data_managers.append(data_manager)
    datasets.append(data_manager.load_data())
    if data_split == 'test':
        eval_data_manager = VOC(args.data_path, data_split, name=data_name, evaluate=True)
        eval_datasets.append(eval_data_manager.load_data())

# instantiating model
num_classes = data_managers[0].num_classes
class_names = data_managers[0].class_names
model = SSD300(num_classes, base_weights='VGG', head_weights=None)
model.summary()

# compile model with loss and optimizer
loss = MultiBoxLoss()

losses = [loss.localization,
          loss.positive_classification,
          loss.negative_classification]

# metrics
metrics = {'boxes': losses}

model.compile(optimizer, loss.compute_loss, metrics)

# setting data augmentation pipeline
augmentators = []
for split in ['train', 'val']:
    augmentator = DetectionAugmentation(model.prior_boxes, num_classes, split)
    augmentators.append(augmentator)

# setting sequencers
sequencers = []
for data, augmentator in zip(datasets, augmentators):
    sequencer = ProcessingSequencer(augmentator, args.batch_size, data)
    sequencers.append(sequencer)

# setting callbacks
model_path = os.path.join(args.save_path, model.name)
if not os.path.exists(model_path):
    os.makedirs(model_path)
log = CSVLogger(os.path.join(model_path, model.name + '-optimization.log'))
save_path = os.path.join(model_path, 'weights.{epoch:02d}-{val_loss:.2f}.hdf5')
checkpoint = ModelCheckpoint(save_path, verbose=1, save_weights_only=True)
schedule = LearningRateScheduler(
    args.learning_rate, args.gamma_decay, args.scheduled_epochs)

detector = SingleShotInference(model, class_names, 0.01, 0.45)
evaluate = EvaluateMAP(class_names, eval_datasets[0], args.eval_per_epoch, detector)
callbacks = [checkpoint, log, schedule, evaluate]

# training
model.fit_generator(
    sequencers[0],
    steps_per_epoch=args.steps_per_epoch,
    epochs=args.num_epochs,
    verbose=1,
    callbacks=callbacks,
    validation_data=sequencers[1],
    use_multiprocessing=True,
    workers=4)
