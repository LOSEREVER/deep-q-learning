import random
import zmq
import os
import json
import experience_pb2
from collections import deque


import gym
import numpy as np
from tensorflow.keras.layers import Dense
from tensorflow.keras.models import Sequential
from tensorflow.keras.optimizers import Adam


class DQNAgent:
    def __init__(self, state_size, action_size):
        self.state_size = state_size
        self.action_size = action_size
        self.replay_buffer = deque(maxlen=2000)
        self.gamma = 0.95  # Discount Rate
        self.epsilon = 1.0  # Exploration Rate
        self.epsilon_min = 0.01
        self.epsilon_decay = 0.995
        self.learning_rate = 0.001
        self.model = self._build_model()

    def _build_model(self):
        """Build Neural Net for Deep Q-learning Model"""

        model = Sequential()
        model.add(Dense(24, input_dim=self.state_size, activation='relu'))
        model.add(Dense(24, activation='relu'))
        model.add(Dense(self.action_size, activation='linear'))
        model.compile(loss='mse', optimizer=Adam(lr=self.learning_rate))
        return model

    def memorize(self, state, action, reward, next_state, done):
        self.replay_buffer.append((state, action, reward, next_state, done))

    def replay(self, batch_size):
        minibatch = random.sample(self.replay_buffer, batch_size)
        for state, action, reward, next_state, done in minibatch:
            target = reward
            if not done:
                target += self.gamma * np.amax(self.model.predict(next_state)[0])
            target_f = self.model.predict(state)
            target_f[0][action] = target
            self.model.fit(state, target_f, epochs=1, verbose=0)
        if self.epsilon > self.epsilon_min:
            self.epsilon *= self.epsilon_decay

    def load(self, name):
        self.model.load_weights(name)

    def save(self, name):
        self.model.save_weights(name)


if __name__ == '__main__':
    env = gym.make('CartPole-v1')
    state_size = env.observation_space.shape[0]
    action_size = env.action_space.n

    agent = DQNAgent(state_size, action_size)

    os.environ['KMP_WARNINGS'] = '0'
    socket = zmq.Context().socket(zmq.ROUTER)
    socket.bind("tcp://*:6080")

    model_path = "./model_weights"
    if os.path.exists(model_path):
        os.system("rm -rf " + model_path)
    os.mkdir(model_path)

    batch_size = 32
    num_episodes = 1000
    for e in range(num_episodes):
        state = env.reset()
        state = np.reshape(state, [1, state_size])
        print("learner -- train episode {}".format(e))
        for time in range(500):
            id, raw_data = socket.recv_multipart()
            data = experience_pb2.Exper()
            data.ParseFromString(raw_data)
            data = {
                "now_state": [data.now_state.pos],
                "action": data.action,
                "reward": data.reward,
                "next_state": [data.next_state.pos],
                "done": data.done,
            }

            agent.memorize(np.array(data["now_state"]), data["action"], data["reward"], np.array(data["next_state"]), data["done"])
            if data["done"]:
                break
            if len(agent.replay_buffer) > batch_size:
                agent.replay(batch_size)
                # agent.save(model_path + "/syf-eposide_{}-time_{}.h5".format(e, time))
                # with open(model_path + "/syf-eposide_{}-time_{}.h5".format(e, time), "rb") as file:
                #     socket.send_multipart([id, file.read()])

        if e % 3 == 0:
            print("learner -- send model")
            agent.save(model_path + "/syf-eposide_{}.h5".format(e, time))
            with open(model_path + "/syf-eposide_{}.h5".format(e, time), "rb") as file:
                socket.send_multipart([id, file.read()])

