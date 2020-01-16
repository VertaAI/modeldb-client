import pytest

import six


class TestKeras:
    def test_sequential_api(self, experiment_run):
        verta_integrations_keras = pytest.importorskip("verta.integrations.keras")
        keras = verta_integrations_keras.keras  # use same Keras imported by Verta
        np = pytest.importorskip("numpy")

        # adapted from https://keras.io/getting-started/sequential-model-guide/
        ## define hyperparameters
        samples = 1000
        num_classes = 10
        num_hidden = 64
        fc_activation = "relu"
        dropout_rate = .5
        batch_size = 128
        epochs = 3
        loss = "categorical_crossentropy"
        optimizer = "Adam"
        ## create dummy data
        x_train = np.random.random((samples, 20))
        y_train = keras.utils.to_categorical(np.random.randint(num_classes, size=(samples, 1)), num_classes=num_classes)
        ## build model
        model = keras.models.Sequential()
        model.add(keras.layers.Dense(num_hidden, activation=fc_activation, input_dim=20))
        model.add(keras.layers.Dropout(dropout_rate))
        model.add(keras.layers.Dense(num_hidden, activation=fc_activation))
        model.add(keras.layers.Dropout(dropout_rate))
        model.add(keras.layers.Dense(num_classes, activation="softmax"))
        ## train model
        model.compile(loss=loss,
                      optimizer=optimizer,
                      metrics=["accuracy"])
        model.fit(x_train, y_train,
                  epochs=epochs,
                  batch_size=batch_size,
                  callbacks=[verta_integrations_keras.VertaCallback(experiment_run)])

        logged_hyperparams = experiment_run.get_hyperparameters()
        assert logged_hyperparams['batch_size'] == batch_size
        assert logged_hyperparams['epochs'] == epochs
        assert logged_hyperparams['loss'] == loss
        assert logged_hyperparams['optimizer'] == optimizer
        assert logged_hyperparams['samples'] == samples
        assert "dense" in logged_hyperparams['layer_0_name']
        assert logged_hyperparams['layer_0_size'] == num_hidden
        assert logged_hyperparams['layer_0_activation'] == fc_activation
        assert "dropout" in logged_hyperparams['layer_1_name']
        assert logged_hyperparams['layer_1_dropoutrate'] == dropout_rate
        assert "dense" in logged_hyperparams['layer_2_name']
        assert logged_hyperparams['layer_2_size'] == num_hidden
        assert logged_hyperparams['layer_2_activation'] == fc_activation
        assert "dropout" in logged_hyperparams['layer_3_name']
        assert logged_hyperparams['layer_3_dropoutrate'] == dropout_rate
        assert "dense" in logged_hyperparams['layer_4_name']
        assert logged_hyperparams['layer_4_size'] == num_classes
        assert logged_hyperparams['layer_4_activation'] == "softmax"
        logged_observations = experiment_run.get_observations()
        assert 'acc' in logged_observations or 'accuracy' in logged_observations
        assert 'loss' in logged_observations


    def test_functional_api(self, experiment_run):
        verta_integrations_keras = pytest.importorskip("verta.integrations.keras")
        keras = verta_integrations_keras.keras  # use same Keras imported by Verta
        np = pytest.importorskip("numpy")

        # also adapted from https://keras.io/getting-started/sequential-model-guide/
        ## define hyperparameters
        samples = 1000
        num_classes = 10
        num_hidden = 64
        fc_activation = "relu"
        dropout_rate = .5
        batch_size = 128
        epochs = 3
        loss = "categorical_crossentropy"
        optimizer = "Adam"
        ## create dummy data
        x_train = np.random.random((samples, 20))
        y_train = keras.utils.to_categorical(np.random.randint(num_classes, size=(samples, 1)), num_classes=num_classes)
        ## build model
        inputs = keras.layers.Input(shape=(20,))
        output_1 = keras.layers.Dense(num_hidden, activation="relu", input_dim=20)(inputs)
        dropout_1 = keras.layers.Dropout(dropout_rate)(output_1)
        output_2 = keras.layers.Dense(num_hidden, activation="relu")(dropout_1)
        dropout_2 = keras.layers.Dropout(dropout_rate)(output_2)
        predictions = keras.layers.Dense(num_classes, activation="softmax")(dropout_2)
        model = keras.models.Model(inputs=inputs, outputs=predictions)
        ## train model
        model.compile(loss=loss,
                      optimizer=optimizer,
                      metrics=["accuracy"])
        model.fit(x_train, y_train,
                  epochs=epochs,
                  batch_size=batch_size,
                  callbacks=[verta_integrations_keras.VertaCallback(experiment_run)])

        logged_hyperparams = experiment_run.get_hyperparameters()
        assert logged_hyperparams['batch_size'] == batch_size
        assert logged_hyperparams['epochs'] == epochs
        assert logged_hyperparams['loss'] == loss
        assert logged_hyperparams['optimizer'] == optimizer
        assert logged_hyperparams['samples'] == samples
        assert "input" in logged_hyperparams['layer_0_name']
        assert "dense" in logged_hyperparams['layer_1_name']
        assert logged_hyperparams['layer_1_size'] == num_hidden
        assert logged_hyperparams['layer_1_activation'] == fc_activation
        assert "dropout" in logged_hyperparams['layer_2_name']
        assert logged_hyperparams['layer_2_dropoutrate'] == dropout_rate
        assert "dense" in logged_hyperparams['layer_3_name']
        assert logged_hyperparams['layer_3_size'] == num_hidden
        assert logged_hyperparams['layer_3_activation'] == fc_activation
        assert "dropout" in logged_hyperparams['layer_4_name']
        assert logged_hyperparams['layer_4_dropoutrate'] == dropout_rate
        assert "dense" in logged_hyperparams['layer_5_name']
        assert logged_hyperparams['layer_5_size'] == num_classes
        assert logged_hyperparams['layer_5_activation'] == "softmax"
        logged_observations = experiment_run.get_observations()
        assert 'acc' in logged_observations or 'accuracy' in logged_observations
        assert 'loss' in logged_observations
