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
        loss = "CategoricalCrossentropy"
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
        model.compile(loss=getattr(keras.losses, loss)(),
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
        model.compile(loss=getattr(keras.losses, loss),
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


class TestTensorFlow:
    def test_estimator_hook(self, experiment_run):
        verta_integrations_tensorflow = pytest.importorskip("verta.integrations.tensorflow")
        VertaHook = verta_integrations_tensorflow.VertaHook

        np = pytest.importorskip("numpy")
        pd = pytest.importorskip("pandas")
        tf = pytest.importorskip("tensorflow")

        # adapted from https://www.tensorflow.org/tutorials/estimator/linear
        samples = 5
        num_features = 3

        data_df = pd.DataFrame(
            data=np.random.random(size=(samples, num_features))*100,
            columns=map(str, range(num_features))
        )
        label_series = pd.Series(np.random.randint(0, 2, size=samples))

        feature_columns = []
        for feature_name in data_df.columns:
            feature_columns.append(tf.feature_column.numeric_column(feature_name, dtype=tf.float32))

        def train_input_fn():
            return tf.data.Dataset.from_tensor_slices((dict(data_df), label_series)).batch(32)

        linear_est = tf.estimator.LinearClassifier(feature_columns=feature_columns)
        linear_est.train(train_input_fn, hooks=[VertaHook(experiment_run, every_n_steps=1)])

        assert 'loss' in experiment_run.get_observations()


class TestXGBoost:
    def test_callback(self, experiment_run):
        verta_integrations_xgboost = pytest.importorskip("verta.integrations.xgboost")
        verta_callback = verta_integrations_xgboost.verta_callback

        xgb = pytest.importorskip("xgboost")
        np = pytest.importorskip("numpy")

        samples = 5
        num_features = 3
        X = np.random.random(size=(samples, num_features))*1000
        y = np.random.randint(0, 10, size=(samples,))
        train_dataset_name = "train"
        dtrain = xgb.DMatrix(X, label=y)

        params = {
            'eta': 0.5,
            'max_depth': 3,
            'num_class': 10,
            'eval_metric': ["merror", "mlogloss"],
        }
        num_rounds = 3

        bst = xgb.train(
            params, dtrain,
            num_boost_round=num_rounds,
            evals=[(dtrain, train_dataset_name)],
            callbacks=[verta_callback(experiment_run)],
        )

        observations = experiment_run.get_observations()
        for eval_metric in params['eval_metric']:
            assert '{}-{}'.format(train_dataset_name, eval_metric) in observations


class TestPyTorch:
    def test_hook(self, experiment_run):
        verta_integrations_torch = pytest.importorskip("verta.integrations.torch")
        verta_hook = verta_integrations_torch.verta_hook

        np = pytest.importorskip("numpy")
        pd = pytest.importorskip("pandas")
        torch = pytest.importorskip("torch")

        samples = 5
        num_features = 3
        num_classes = 10
        X = np.random.randint(0, 17, size=(samples, num_features))
        y = np.random.randint(0, num_classes, size=(samples,))
        X = torch.tensor(X, dtype=torch.float)
        y = torch.tensor(y, dtype=torch.long)

        hidden_size = 512
        dropout = 0.2

        class Net(torch.nn.Module):
            def __init__(self, hidden_size, dropout):
                super(Net, self).__init__()
                self.fc      = torch.nn.Linear(num_features, hidden_size)
                self.dropout = torch.nn.Dropout(dropout)
                self.output  = torch.nn.Linear(hidden_size, num_classes)

            def forward(self, x):
                x = x.view(x.shape[0], -1)  # flatten non-batch dimensions
                x = torch.nn.functional.relu(self.fc(x))
                x = self.dropout(x)
                x = torch.nn.functional.softmax(self.output(x), dim=-1)
                return x

        model = Net(hidden_size, dropout)
        model.register_forward_hook(verta_hook(experiment_run))
        output = model(X)

        logged_hyperparams = experiment_run.get_hyperparameters()

        assert logged_hyperparams['layer_0_name'] == "Linear"
        assert logged_hyperparams['layer_0_in_features'] == num_features
        assert logged_hyperparams['layer_0_out_features'] == hidden_size

        assert logged_hyperparams['layer_1_name'] == "Dropout"
        assert logged_hyperparams['layer_1_p'] == dropout

        assert logged_hyperparams['layer_2_name'] == "Linear"
        assert logged_hyperparams['layer_2_in_features'] == hidden_size
        assert logged_hyperparams['layer_2_out_features'] == num_classes
