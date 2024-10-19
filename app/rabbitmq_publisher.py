import pika
import json

# creates queue and sends a task to it
def send_transformation_task(image_id: int, transformations:dict, s3_uri: str):
    connection = pika.BlockingConnection(pika.ConnectionParameters('rabbitmq',  # rabbitmq for docker, localhost for running directly
                                                                    port=5672,        # RabbitMQ port (default is 5672)
    credentials=pika.PlainCredentials('guest', 'guest') )) # RabbitMQ credentials))
    print('got here')
    channel = connection.channel()
    print('1')
    #declare the queue
    channel.queue_declare(queue='image_transformations', durable=True)
    print('2')
    # create a message
    print(image_id, transformations)
    message = json.dumps({'image_id': image_id, 'transformations': transformations, 's3_uri': s3_uri})
    print('3')
    # publish the message to the queue
    channel.basic_publish(exchange='', routing_key='image_transformations', body=message)
    print('message sent')

    connection.close()
