# import the necessary packages
#from keras.preprocessing.image import img_to_array
from tensorflow.keras.preprocessing.image import img_to_array
from keras.applications import imagenet_utils
from PIL import Image
import numpy as np
import settings
import helpers
import flask
import redis
import uuid
import time
import json
import io

# initialize our Flask application and Redis server
app = flask.Flask(__name__)
db = redis.StrictRedis(host=settings.REDIS_HOST,
	port=settings.REDIS_PORT, username=settings.REDIS_USERNAME,
	password=settings.REDIS_PASSWORD, db=settings.REDIS_DB)

def prepare_image(image, target):
	# if the image mode is not RGB, convert it
	if image.mode != "RGB":
		image = image.convert("RGB")

	# resize the input image and preprocess it
	image = image.resize(target)
	image = img_to_array(image)
	image = np.expand_dims(image, axis=0)
	image = imagenet_utils.preprocess_input(image)

	# return the processed image
	return image

@app.route("/")
def homepage():
	return "Welcome to the PyImageSearch Keras REST API!"

@app.route("/predict", methods=["POST"])
def predict():
	# initialize the data dictionary that will be returned from the
	# view
	data = {"success": False}

	# ensure an image was properly uploaded to our endpoint
	if flask.request.method == "POST":
		if flask.request.files.get("image"):
			# read the image in PIL format and prepare it for
			# classification
			image = flask.request.files["image"].read()
			image = Image.open(io.BytesIO(image))
			image = prepare_image(image,
				(settings.IMAGE_WIDTH, settings.IMAGE_HEIGHT))

			# ensure our NumPy array is C-contiguous as well,
			# otherwise we won't be able to serialize it
			image = image.copy(order="C")

			# generate an ID for the classification then add the
			# classification ID + image to the queue
			k = str(uuid.uuid4())

			# Create a pubsub instance for this request
			p = db.pubsub()

			# Subscribe to keyspace notifications for our specific key
			# BEFORE queueing work to avoid missing the notification
			p.psubscribe(f"__keyspace@0__:{k}")

			image = helpers.base64_encode_image(image)
			d = {"id": k, "image": image}
			db.rpush(settings.IMAGE_QUEUE, json.dumps(d))

			# Wait for notification that the result is ready
			# Use notifications with polling fallback for reliability
			timeout = 30.0  # 30 second timeout
			notification_received = False

			# Try to get notification
			print(f"* Waiting for result notification for job {k}...")
			message = p.get_message(timeout=timeout)

			if message is not None and message.get('type') == 'pmessage':
				notification_received = True
				print(f"* Received notification for job {k}")

			# Attempt to grab the output predictions
			output = db.get(k)

			# Fallback to polling if notification was missed or result not ready
			poll_attempts = 0
			max_poll_attempts = 10
			while output is None and poll_attempts < max_poll_attempts:
				print(f"* Polling for result (attempt {poll_attempts + 1}/{max_poll_attempts})...")
				time.sleep(settings.CLIENT_SLEEP)
				output = db.get(k)
				poll_attempts += 1

			# Clean up pubsub
			p.punsubscribe(f"__keyspace@0__:{k}")
			p.close()

			# check to see if our model has classified the input image
			if output is not None:
				# add the output predictions to our data
				# dictionary so we can return it to the client
				output = output.decode("utf-8")
				data["predictions"] = json.loads(output)

				# delete the result from the database
				db.delete(k)

				# indicate that the request was a success
				data["success"] = True
			else:
				print(f"* ERROR: Timeout waiting for job {k}")
				data["error"] = "Prediction timeout"

	# return the data dictionary as a JSON response
	return flask.jsonify(data)

# for debugging purposes, it's helpful to start the Flask testing
# server (don't use this for production
if __name__ == "__main__":
	print("* Starting web service...")
	print("* IMPORTANT: Make sure Redis keyspace notifications are enabled:")
	print("*   Run in Redis CLI: CONFIG SET notify-keyspace-events KEA")
	app.run()
