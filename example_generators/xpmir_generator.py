import ir_datasets
from example_generators import Example

class XPMIRExampleGenerator():

    def __init__(self, dataset_id):
        self.dataset_id = dataset_id
        self.dm_id = f'''irds.{self.dataset_id.replace("/", ".")}'''
        self.dataset = ir_datasets.load(dataset_id)
        try:
            self.docs_parent_id = ir_datasets.docs_parent_id(dataset_id)
        except:
            self.docs_parent_id = None



    def generate_scoreddocs(self):
        return Example(f'''
import datamaestro # Supposes experimaestro-ir be installed

run = datamaestro.prepare_dataset('{self.dm_id}.scoreddocs') # AdhocRun
# A run is a generic object, and is specialized into final classes
# e.g. TrecAdhocRun 
''', message_html='This examples requires that <a href="https://experimaestro-ir.readthedocs.io/">experimaestro-ir</a> be installed. For more information about the returned object, see the documentation about <a href="https://datamaestro-text.readthedocs.io/en/latest/api/ir.html#datamaestro_text.data.ir.AdhocRun">AdhocRun</a>')

    def generate_docpairs(self):
        return Example(f'''
import datamaestro # Supposes experimaestro-ir be installed

docpairs = datamaestro.prepare_dataset('{self.dm_id}.docpairs')
next(docpairs.iter())  # Display the first triplet
''', message_html='This examples requires that <a href="https://experimaestro-ir.readthedocs.io/">experimaestro-ir</a> be installed. For more information about the returned object, see the documentation about <a href="https://datamaestro-text.readthedocs.io/en/latest/api/ir.html#datamaestro_text.data.ir.TrainingTriplets">TrainingTriplets</a>')


    def generate_qlogs(self):
        return None

    def generate_docs(self):
        dm_id = f'{self.dm_id}.documents' if self.docs_parent_id == self.dm_id else self.dm_id
        return Example(code=f'''
from datamaestro import prepare_dataset
dataset = prepare_dataset('{dm_id}')
for doc in dataset.iter_documents():
    print(doc)  # an AdhocDocumentStore
    break
''', message_html='This examples requires that <a href="https://experimaestro-ir.readthedocs.io/">experimaestro-ir</a> be installed. For more information about the returned object, see the documentation about <a href="https://datamaestro-text.readthedocs.io/en/latest/api/ir.html#datamaestro_text.data.ir.AdhocDocumentStore">AdhocDocumentStore</a>')

    def generate_queries(self):
        return Example(code=f'''
from datamaestro import prepare_dataset
topics = prepare_dataset('{self.dm_id}.queries')  # AdhocTopics
for topic in topics.iter():
    print(topic)  # An AdhocTopic

''', message_html='This examples requires that <a href="https://experimaestro-ir.readthedocs.io/">experimaestro-ir</a> be installed. For more information about the returned object, see the documentation about <a href="https://datamaestro-text.readthedocs.io/en/latest/api/ir.html#datamaestro_text.data.ir.AdhocTopics">AdhocTopics</a>.')

    def generate_qrels(self):
        return Example(f'''
from datamaestro import prepare_dataset
qrels = prepare_dataset('{self.dm_id}.qrels')  # AdhocAssessments
for topic_qrels in qrels.iter():
    print(topic_qrels)  # An AdhocTopic
''', message_html='This examples requires that <a href="https://experimaestro-ir.readthedocs.io/">experimaestro-ir</a> be installed. For more information about the returned object, see the documentation about <a href="https://datamaestro-text.readthedocs.io/en/latest/api/ir.html#datamaestro_text.data.ir.AdhocAssessments">AdhocAssessments</a>.')
