
from kafka import KafkaConsumer, KafkaProducer
import time
import json

def create_response(ID):
	producer = KafkaProducer(bootstrap_servers='localhost:9092', value_serializer=lambda v: json.dumps(v).encode('utf-8'))
	data['ID'] = ID
	data['response'] = "Received message: " + str(ID)
	producer.send("CLI_response", data)
	producer.flush(30)

consumer = KafkaConsumer(bootstrap_servers='localhost:9092', auto_offset_reset='earliest', value_deserializer=lambda m: json.loads(m.decode('utf-8')))
consumer.subscribe("CLI")
while True:
	for msg in consumer:
		assert isinstance(msg.value, dict)
		data = msg.value
		print("Received Data: " + str(data))
		create_response(data['ID'])
	time.sleep(2)



