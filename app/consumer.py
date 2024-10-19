import pika
import json
import io
import time
from PIL import Image, ImageOps
import pika.exceptions
from .routes import get_image_from_s3, s3, BUCKET_NAME


# uses Pillow to transform the image as requested by the user

def alter_image(im, img_request, s3_uri):
    print('now lets transform')
    # transformation_dict = img_request.model_dump()
    transformations = img_request['transformations']
    print(transformations)
    try:
        if transformations['resize'] is not None:
            width = transformations['resize']['width']
            height = transformations['resize']['height']
            im = im.resize((width, height))
        if transformations['crop'] is not None:
            width = transformations['crop']['width']
            height = transformations['crop']['height']
            x = transformations['crop']['x']
            y = transformations['crop']['y']
            im = im.crop(( x, y, x + width, y + height))
        if transformations['filters'] is not None:
            if transformations['filters']["grayscale"] == True:
                im = ImageOps.grayscale(im)
        if transformations['rotate'] is not None:
            degree = transformations['rotate']
            im = im.rotate(degree)
    except Exception as e:
        print('error transforming in consumer', e)
    try:
        img_byte_arr = io.BytesIO()
        im.save(img_byte_arr, format='JPEG')  # or 'PNG' based on your requirement
        img_byte_arr.seek(0)  # Move to the beginning of the BytesIO object
        s3.upload_fileobj(img_byte_arr, BUCKET_NAME, s3_uri)
    except Exception as e:
        print('error consumer saving', e)
    return im

def callback(ch, method, properties, body):
    print('msg processing')
    message = json.loads(body)
    image_id = message.get('image_id')
    transformations = message.get('transformations')
    s3_uri = message.get('s3_uri')
    
    # Retry fetching the image from S3
    for attempt in range(3):  # Retry 3 times
        try:
            print(f"Attempting to fetch image from S3: {s3_uri} (Attempt {attempt + 1})")
            im = get_image_from_s3(s3_uri)
            break  # Exit the loop if successful
        except Exception as e:
            print(f"Error retrieving image from S3: {e}. Retrying...")
            time.sleep(2)  # Wait before retrying
    else:
        # If all retries fail, nack the message and return
        print(f"Failed to retrieve image from S3 after 3 attempts: {s3_uri}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
        time.sleep(5)
        return

    # Process the image
    try: 
        alter_image(im, transformations, s3_uri)
        print(f"Image {image_id} successfully transformed and saved to S3")
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        print(f"Error when trying to alter image {image_id}: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
        time.sleep(1)  # Back off before retrying


def consume_task():
    print('consuming')
    while True:
        try:
            connection = pika.BlockingConnection(pika.ConnectionParameters(host='rabbitmq'))
            channel = connection.channel()
        except pika.exceptions.AMQPConnectionError:
                print('Error connecting to RabbitMQ, retrying in 5 seconds...')
                time.sleep(5)
                continue 

        #declare the queue
        channel.queue_declare(queue='image_transformations', durable=True)
        print('got to consumer')
        # consume task
        channel.basic_consume(queue='image_transformations', on_message_callback=callback)

        print('waiting for tasks...')
        try:
            channel.start_consuming()
        except pika.exceptions.ConnectionClosedByBroker:
            print('Connection closed by broker, reconnecting')
        except KeyboardInterrupt:
            print("consumer stopped")
            break

if __name__ == '__main__':
    print('hiya')
    consume_task()