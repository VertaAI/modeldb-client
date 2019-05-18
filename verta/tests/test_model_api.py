import pytest
from verta import utils as verta_utils
from pprint import pprint
import json
from deepdiff import DeepDiff

class TestModelAPI:
    class ModelAPITestCase:
        def __init__(self, model, sample_input, sample_output, 
                    sample_rest_call, true_model_api):
            self.model = model
            self.sample_input = sample_input
            self.sample_output = sample_output
            self.sample_rest_call = sample_rest_call
            self.true_model_api = true_model_api
            
        def __str__(self):
            return self.model.__str__() + "\n" +  \
            self.sample_input.__str__() + "\n" +  \
            self.sample_output.__str__() + "\n" +   \
            self.sample_rest_call.__str__() + "\n" + \
            self.true_model_api.__str__()

    def generate_log_reg_test_case(self):
        from sklearn import linear_model
        import pandas as pd
        import numpy as np
        
        data_train = pd.DataFrame([[1, 2, 3, 0], [4, 5, 6, 0], [7, 8, 9, 1]], columns=['a', 'b', 'c', 'target'])
        data_test = pd.DataFrame([[11, 12, 13, 0], [14, 15, 16, 1]], columns=['a', 'b', 'c', 'target'])

        logreg = linear_model.LogisticRegression()
        logreg.fit(data_train[["a", "b", "c"]], data_train["target"])
        
        sample_input = [[1, 2, 3]]
        sample_output = [0]
        
        rest_call = {
            'token' : 'some-token',
            'data' : '[[1, 2, 3]]'
        }
        
        output_type = {
            "name" : "random_name1",
            "type" : "VertaList",
            "value" : [
                {
                    "name" : "target",
                    "type" : "VertaFloat",
                    # "value" : 0.5
                }
            ]
        }
        
        input_type = {
            "name" : "random_name1",
            "type" : "VertaList",
            "value" : [
                {
                    "name" : "random_name2",
                    "type" : "VertaList",
                    "value" : [
                        {
                            "name" : "a",
                            "type" : "VertaFloat",
                            # "value" : 23
                        },
                        {
                            "name" : "b",
                            "type" : "VertaFloat",
                            # "value" : 24   
                        },
                        {
                            "name" : "c",
                            "type" : "VertaFloat",
                            # "value" : 3   
                        }
                    ]
                }
            ]
            
        }
        
        spec = {"output" : output_type, "input" : input_type}
        
        return self.ModelAPITestCase(
            model=logreg,
            sample_input=sample_input,
            sample_output=sample_output,
            sample_rest_call=rest_call,
            true_model_api=spec
        )

    def generate_text_pipeline_1_test_case(self):
        import sklearn
        import pandas as pd
        from sklearn.feature_extraction.text import CountVectorizer
        from sklearn.feature_extraction.text import TfidfTransformer
        from sklearn.naive_bayes import MultinomialNB
        from sklearn.pipeline import Pipeline
        
        data_train = pd.DataFrame([
            ["mary had a little lamb", 1], 
            ["the lamb's fleece was white as snow", 1], 
            ["sheila was ought to go", 0]], columns=['text', 'target'])
        
        data_test = pd.DataFrame([
            ["the lamb was ought to go", 1], 
            ["mary had a little lamb", 1]], columns=['text', 'target'])

        pipeline = Pipeline([
            ('vectorizer', CountVectorizer()),
            ('tfidf', TfidfTransformer()),
            ('clf', MultinomialNB()),
        ])
        pipeline.fit(data_train["text"], data_train["target"])

        sample_input = ["mary had a little lamb"]
        sample_output = [1]
        
        rest_call = {
            'token' : 'some-token',
            'data' : '["mary had a little lamb"]',
        }
        
        output_type = {
            "name" : "random_name1",
            "type" : "VertaList",
            "value" : [
                {
                    "name" : "target",
                    "type" : "VertaFloat",
                    # "value" : 0.5,
                }
            ]
        }
        
        input_type = {
            "name" : "random_name2",
            "type" : "VertaList",
            "value" : [
                {
                    "name" : "input",
                    "type" : "VertaString",
                    # "value" : "mary had a little lamb",
                },
            ]
        }
        
        spec = {"output" : output_type, "input" : input_type}
        
        return self.ModelAPITestCase(
            model=pipeline,
            sample_input=sample_input,
            sample_output=sample_output,
            sample_rest_call=rest_call,
            true_model_api=spec
        )

    def helper(self, test_case):
        '''
            a. Define the Python model we are working on and the inputs and outputs to the predict function
            b. Define REST call
            c. Define the model API for it (Ground Truth)
            d. Use utility to generate the model API from the data in and out
            e. Given the REST API and the model API, turn them into the prediction expected by the model
        '''
        # assert that the model and sample input and output are all valid
        assert test_case.model.predict(test_case.sample_input) == test_case.sample_output
        
        # TODO: assert that true_model_api is valid (not implemented in ModelAPI yet)
        
        # generate the model_api
        generated_api = verta_utils.ModelAPI(test_case.sample_input, test_case.sample_output).to_dict()
        pprint(test_case.true_model_api)
        
        # compare generated and true model api
        pprint(DeepDiff(generated_api, test_case.true_model_api))
        
        # process REST call
        rest_generated_input = json.loads(test_case.sample_rest_call['data'])
        assert rest_generated_input == test_case.sample_input
    
    def test_log_reg(self):
        self.helper(self.generate_log_reg_test_case())

    def test_text_pipeline_1(self):
        self.helper(self.generate_text_pipeline_1_test_case())