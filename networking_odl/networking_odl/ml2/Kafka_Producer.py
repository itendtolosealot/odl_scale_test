import time

from kafka import KafkaProducer, KafkaConsumer
from kafka.admin import KafkaAdminClient, NewTopic
from kafka.cluster import ClusterMetadata
from kafka.errors import TopicAlreadyExistsError
import json
import argparse
import uuid
'''
def create_topics():
	admin_client = KafkaAdminClient(bootstrap_servers="localhost:9092", client_id='test')
	consumer = KafkaConsumer(bootstrap_servers="localhost:9092", client_id="topic_deleter")
	topic_str_set= consumer.topics()
	print("Existing topics: " + str(topic_str_set))
	response = admin_client.delete_topics(list(topic_str_set))
	admin_client.flush
	while (len(topic_str_set) != 0):
		topic_str_set= consumer.topics()
		time.sleep(2)
	print("Existing topics: " + str(topic_str_set))
	topic_list = []
	try:
		topic_list.append(NewTopic(name="CLI", num_partitions=1, replication_factor=1))
		admin_client.create_topics(new_topics=topic_list, validate_only=False)
		admin_client.close()
	except TopicAlreadyExistsError as ex:
		print("Topic already exists. Ignoring topic creation")
'''

def parse_arguments():
	parser = argparse.ArgumentParser(description="Create a container & attach it to the ovs switch")
	subparser = parser.add_subparsers(dest="command")
	parser_computes = subparser.add_parser("compute")
	parser_computes.add_argument("-a", '--action', action='store', dest="action", choices=['start', 'stop', 'status'], help="Start/Stop computes")
	parser_computes.add_argument('-ctrl_ip', '--controllerip', dest="controllerip", help="IP address of the controller")
	parser_computes.add_argument('-n', '--numcomputes', dest="numcomputes", help="Number of computes that need to be started")


	parser_test = subparser.add_parser("test")
	parser_test.add_argument("-r","--resource", choices=['elan','router'],action='store', dest="resource", help='Resources to be tested' )
	parser_test.add_argument('-a',"--action", choices=['start', 'stop'], action='store', dest="action", help='Start/Stop tests')

	parser_mip = subparser.add_parser('mip')
	parser_mip.add_argument('-a',"--action", choices=['create', 'delete'], action='store', dest="action", help='Start/Stop tests')
	parser_mip.add_argument('-n','--nummips', action='store', dest="nummips", help='Number of MIPs')
	args = parser.parse_args()
	return args

def compute_parse(args):
	data = dict()
	data['command'] = args.command
	data['action'] = args.action
	if(args.controllerip):
		data['controller_ip']=args.controllerip
	if(args.numcomputes):
		data['numcomputes']=args.numcomputes
	return data

def test_parse(args):
	data = dict()
	data['command'] = args.command
	data['resource'] =args.resource
	data['action'] = args.action
	return data

def mip_parse(args):
	data = dict()
	data['command'] = args.command
	data['action'] = args.action
	if(args.nummips):
		data['nummips']=args.nummips
	return data

def wait_for_response(ID):
	consumer = KafkaConsumer(bootstrap_servers='localhost:9092', auto_offset_reset='earliest', value_deserializer=lambda m: json.loads(m.decode('utf-8')))
	consumer.subscribe("CLI_response")
	for msg in consumer:
		assert isinstance(msg.value, dict)
		data = msg.value
		print("Received Data: " + str(data))
		if (data['ID'] == ID):
			print("Received response for query: " + str(ID))
			return data['response']

if __name__ == '__main__':
	parsing_dict = {
		"compute": compute_parse,
		"test": test_parse,
		"mip": mip_parse
	}
	args = parse_arguments()
	#create_topics()
	producer = KafkaProducer(bootstrap_servers='localhost:9092', value_serializer=lambda v: json.dumps(v).encode('utf-8'))
	data = parsing_dict[args.command](args)
	ID = str(uuid.uuid4())
	data['ID'] = ID
	producer.send("CLI", data)
	producer.flush(30)
	print("Sent data: " + str(data))
	response = wait_for_response(ID)
	print(str(response))






