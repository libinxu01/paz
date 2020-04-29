import numpy as np

from ..abstract import Processor
from ..backend.boxes import to_one_hot


class Predict(Processor):
    def __init__(self, model, preprocess=None, postprocess=None):
        super(Predict, self).__init__()
        self.model = model
        self.preprocess = preprocess
        self.postprocess = postprocess

    def call(self, x):
        if self.preprocess is not None:
            x = self.preprocess(x)
        y = self.model.predict(x)
        if self.postprocess is not None:
            y = self.postprocess(y)
        return y


class ToClassName(Processor):
    def __init__(self, labels):
        super(ToClassName, self).__init__()
        self.labels = labels

    def call(self, x):
        return self.labels[np.argmax(x)]


class ExpandDims(Processor):
    def __init__(self, axis):
        super(ExpandDims, self).__init__()
        self.axis = axis

    def call(self, x):
        return np.expand_dims(x, self.axis)


class BoxClassToOneHotVector(Processor):
    """Transform from class index to a one-hot encoded vector.
    # Arguments
        num_classes: Integer. Total number of classes.
        topic: String. Currently valid topics: `boxes`
    """
    def __init__(self, num_classes):
        self.num_classes = num_classes
        super(BoxClassToOneHotVector, self).__init__()

    def call(self, boxes):
        class_indices = boxes[:, 4].astype('int')
        one_hot_vectors = to_one_hot(class_indices, self.num_classes)
        one_hot_vectors = one_hot_vectors.reshape(-1, self.num_classes)
        boxes = np.hstack([boxes[:, :4], one_hot_vectors.astype('float')])
        return boxes


class OutputSelector(Processor):
    """Selects data types (topics) that will be outputted.
    #Arguments
        input_topics: List of strings indicating the keys of data
            dictionary (data topics).
        output_topics: List of strings indicating the keys of data
            dictionary (data topics).
        as_dict: Boolean. If ``True`` output will be a dictionary
            of form {'inputs':list_of_input_arrays,
                     'outputs': list_of_output_arrays}
            If ``False'', output will be of the form
                list_of_input_arrays + list_of_output_arrays
    """
    def __init__(self, input_topics, label_topics):
        self.input_topics, self.label_topics = input_topics, label_topics
        super(OutputSelector, self).__init__()

    def call(self, kwargs):
        inputs, labels = {}, {}
        for topic in self.input_topics:
            inputs[topic] = kwargs[topic]
        for topic in self.label_topics:
            labels[topic] = kwargs[topic]
        return {'inputs': inputs, 'labels': labels}


class SelectElement(Processor):
    def __init__(self, topic, argument):
        super(SelectElement, self).__init__()
        self.topic = topic
        self.argument = argument

    def call(self, kwargs):
        kwargs[self.topic] = kwargs[self.topic][self.argument]
        return kwargs


class Squeeze(Processor):
    """Wrap around numpy `squeeze` due to common use before model predict.
    # Arguments
        expand_dims: Int or list of Ints.
        topic: String.
    """
    def __init__(self, axis, topic):
        super(Squeeze, self).__init__()
        self.axis, self.topic = axis, topic

    def call(self, kwargs):
        kwargs[self.topic] = np.squeeze(kwargs[self.topic], axis=self.axis)
        return kwargs


class Copy(Processor):
    """Copy values from ``input_topic`` to a new ``label_topic``
    # Arguments
        input_topic: String. Topic to copy from.
        label_topic: String. Topic to copy to.
    """
    def __init__(self, input_topic, label_topic):
        super(Copy, self).__init__()
        self.input_topic, self.label_topic = input_topic, label_topic

    def call(self, kwargs):
        kwargs[self.label_topic] = kwargs[self.input_topic].copy()
        return kwargs


class Lambda(object):
    """Applies a lambda function as a processor transformation.
    # Arguments
        function: Function.
        parameters: Dictionary.
        topic: String
    """

    def __init__(self, function, parameters, topic):
        self.function = function
        self.parameters = parameters
        self.topic = topic

    def __call__(self, kwargs):
        data = self.function(kwargs[self.topic], **self.parameters)
        kwargs[self.topic] = data
        return kwargs
