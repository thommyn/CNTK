from abc import ABCMeta, abstractmethod

import numpy as np
from gym import spaces

from .shared.discretize import BoxSpaceDiscretizer


class AgentBaseClass(object):
    """Base class for defining an agent."""

    __metaclass__ = ABCMeta

    def __init__(self, o_space, a_space):
        """Constructor for AgentBaseClass."""
        if not isinstance(a_space, spaces.Discrete):
            raise ValueError(
                'Action space {0} incompatible with {1}. (Only supports '
                'Discrete action spaces.)'.format(a_space, self))
        self._num_actions = a_space.n

        # We assume the observation is in one of the following forms:
        # 1. discrete, and takes values from 0 to n - 1
        # 2. can be discretized, and the raw state is converted to an internal
        #    state taking values from 0 to n - 1
        # 3. raw, such as images from Atari games
        #
        # OpenAI gym supports the following observation types:
        # Discrete, Box, MultiBinary, MultiDiscrete and Tuple. Discrete
        # corresponds to case 1. Box, MultiBinary and MultiDiscrete can be
        # either case 2 or 3. Tuple is a mix of case 1, 2 or 3, and is not
        # supported currently.
        #
        # The observation-related parameters are defined as follows:
        # _discrete_observation_space: True for cases 1 and 2, False otherwise.
        #   State is represented by a scalar.
        # _space_discretizer: Not none for case 2 to indicate a conversion on
        #   state is requried. None otherwise.
        # _shape_of_inputs: (n, ) for cases 1 and 2 to indicate it is a vector
        #   of length n. For case 3, it is the shape of array that represents
        #   the state. For example, an image input will have shape denoted as
        #   tuple (channel, width, height).
        if not (isinstance(o_space, spaces.Discrete) or
                isinstance(o_space, spaces.MultiBinary) or
                isinstance(o_space, spaces.Box) or
                isinstance(o_space, spaces.MultiDiscrete)):
            raise ValueError(
                'Unsupported observation space type: {0}'.format(o_space))

        self._space_discretizer = None
        self._discrete_observation_space = \
            isinstance(o_space, spaces.Discrete)
        # Set self._num_states for discrete observation space only.
        # Otherwise set it to None so that an exception will be raised
        # should it be used later in the code.
        self._num_states = \
            o_space.n if self._discrete_observation_space else None

        if (isinstance(o_space, spaces.Discrete) or
            isinstance(o_space, spaces.MultiBinary)):
            self._shape_of_inputs = (o_space.n,)
        else:
            self._shape_of_inputs = o_space.shape

        self._preprocessor = None
        self._best_model = None

    @abstractmethod
    def start(self, state):
        """Start a new episode.

        Return (action, debug_info) tuple where debug_info is a dictionary.
        """
        pass

    @abstractmethod
    def step(self, reward, next_state):
        """Observe one transition and choose an action.

        Return (action, debug_info) tuple where debug_info is a dictionary.
        """
        pass

    @abstractmethod
    def end(self, reward, next_state):
        """Last observed reward/state of the episode (which then terminates)."""
        pass

    @abstractmethod
    def save(self, filename):
        """Save model to file."""
        pass

    @abstractmethod
    def save_parameter_settings(self, filename):
        """Save parameter settings to file."""
        pass

    @abstractmethod
    def set_as_best_model(self):
        """Copy current model to best model."""
        pass

    def enter_evaluation(self):
        """Setup before evaluation."""
        pass

    def exit_evaluation(self):
        """Tear-down after evaluation."""
        pass

    def evaluate(self, o):
        """Choose action for given observation without updating agent's status."""
        a, _ = self._choose_action(self._preprocess(o))
        return a

    @abstractmethod
    def _choose_action(self, state):
        """Choose an action according to the policy.

        Return (action, debug_info) tuple where debug_info is a string.
        """
        pass

    def _discretize_observation_space(self, space, discretization_resolution):
        if isinstance(space, spaces.Box):
            self._space_discretizer = BoxSpaceDiscretizer(
                space,
                discretization_resolution)
            self._discrete_observation_space = True
            self._num_states = self._space_discretizer.num_states
            self._shape_of_inputs = (self._num_states,)
        else:
            raise ValueError(
                "Unsupported space type for discretization: {0}".format(space))

    def _discretize_state_if_necessary(self, state):
        if self._space_discretizer is not None:
            return self._space_discretizer.discretize(state)
        else:
            return state

    def _index_to_vector(self, index, dimension):
        # TODO(maoyi): Use sparse vector
        a = np.zeros(dimension,)
        a[index] = 1
        return a

    def _preprocess(self, state):
        """Preprocess state to generate input to neural network.

        When state is a scalar which is the index of the state space, convert
        it using one-hot encoding.

        For other cases, state and input are the same, roughly.

        CNTK only supports integer, float32 and float64. Performs appropriate
        type conversion as well.
        """
        o = self._discretize_state_if_necessary(state)
        if self._discrete_observation_space:
            o = self._index_to_vector(o, self._num_states)
        if self._preprocessor is not None:
            o = self._preprocessor.preprocess(o)
        if o.dtype.name == 'uint8':
            # This usually happens for image input.
            o = o.astype(int)
        elif o.dtype.name == 'float64':
            # Not absolutely necessary. But functions in CNTK Layers library
            # are of type float32.
            o = o.astype(np.float32)
        return o