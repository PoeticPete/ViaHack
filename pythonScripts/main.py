import face_recognition
import cv2
import pyrebase
import urllib.request
import threading
import time
from pyfcm import FCMNotification

push_service = FCMNotification(api_key="AAAAXcxEn-s:APA91bFNEwRE8zcelyBM8dhbQ1hDPkWXFyK2zN5vnVigp3YRZvOilJJasmCAKmYpDEjbWE4_PF2ZbNBNzy51ppCXKo90NDUrgGYnWAHvnglqXNsjtEXDOBs2bEotcOelZ8f1h_IvFDyy")

# Get a reference to webcam #0 (the default one)
video_capture = cv2.VideoCapture(0)
video_capture.set(3,7680)
video_capture.set(4,4320)

names = []

# Load a sample picture and learn how to recognize it.
# varun_image = face_recognition.load_image_file("faces/Emma")
# varun_face_encoding = face_recognition.face_encodings(varun_image)[0]
# print("HERE!!")
# print(varun_face_encoding)
# second_image = face_recognition.load_image_file("peter2.png")
# second_face_encoding = face_recognition.face_encodings(second_image)[0]

# store face encodings in an array
known_encodings = []
last_sent_notifications = {}


# Initialize some variables
face_locations = []
face_encodings = []
face_names = []
counter = 0
notificationQueue = []
scaling_factor = 2	# scale down the captured image by this much for efficiency

# configure firebase
config = {
	"apiKey": "AIzaSyC3tcDJPD4nXPslkhZ7gscE8p9Im4Gw00s",
	"authDomain": "easy-lock.firebaseapp.com",
  	"databaseURL": "https://easy-lock.firebaseio.com/",
  	"storageBucket": "easy-lock.appspot.com"
}
firebase = pyrebase.initialize_app(config)
db = firebase.database()
storage = firebase.storage()


# ----------FUNCTIONS---------------

'''
    FUNCTION: saves a frame from cv2 to the local disk
'''
def save_frame(filepath, frame):
    cv2.imwrite(filepath, frame)

'''
    FUNCTION: sends a picture to the storage bucket and makes a post to the database
'''
def send_frame_to_database(key, picture_path, name):

    storage.child("images/" + key).put(picture_path)
    url = storage.child("images/" + key).get_url(None)

    upload_dict = {"name": name, "timestamp":{".sv": "timestamp"}, "photoURL": url}
    db.child("savedFrames/door1").child(key).set(upload_dict)

'''
    FUNCTION: sends a push notification to a single device (ie. <name> was seen as your front door)
'''
def send_FCM_Notification(name):
    registration_id = "fMXYRHTn9D8:APA91bFY1VgkqkDWo39QHoEP2PzgCj3auDElvWuftnXiAyMp3cNfgER6Rq2dMLy1J4oWpV2o7vdtdKZoSC_RkmmWMW1F_XdHmUYFFBsz6vjAekA-zweh0-kRMJJBHjht0pvIPoiawyQ4"
#    registration_id = "fiBDcSV80CQ:APA91bHI1diAIhIJfsrlVNo-sFjeafqy-C6a5S4gAe4gDMuCpB5_aOT0Ovh3HtxY8Xa4xKwwfdkh2xq0JlHBVEAY3rjzmBhpZYIGJ0sulrW635y_0jezulhXYujUWjvH2Ge0V1bbe7nQ"
    message_title = "ALERT"
    message_body = name + " was seen at your front door"
    result = push_service.notify_single_device(registration_id=registration_id, message_title=message_title, message_body=message_body)
    last_sent_notifications[name] = time.time()
    print(result)

'''
    FUNCTION: determines if a notification should be sent, once every minute
'''
def should_send_notification(name):
    if name in last_sent_notifications and time.time() - last_sent_notifications[name] < 10:
        return False
    else:
        return True


'''
    FUNCTION: handles the real time firebase data stream. When a new photo is added to the database, it is synced in real time with this computer.
'''
def stream_handler(message):
    print("got a message")
    print(message["event"]) # put
    print(message["path"]) # /-K7yGTTEp7O549EzTYtI

    if message["data"]:
        file_name = "faces/"
        data = message["data"]
#        print(data)

        #  Make sure the data being retrieved is a dictionary
        if type(data) is dict:

            #  If the data returned is a single item
            if "mediaURL" in data:
#                print("SINGLE ITEM")
                mediaURL = str(data["mediaURL"])
                name = str(data["name"])
#                print(mediaURL, name)
                urllib.request.urlretrieve(mediaURL, file_name + name)
                names.append(name)
                known_encodings.append(face_recognition.face_encodings(face_recognition.load_image_file(file_name + name))[0])

            #  If the data returned is a a list of items
            else:
                print("MULTIPLE ITEMS")

                for key,value in data.items():
                    mediaURL = str(value["mediaURL"])
                    name = str(value["name"])
                    print(mediaURL, name)
                    urllib.request.urlretrieve(mediaURL, file_name + name)
                    try:
                        tmp = face_recognition.face_encodings(face_recognition.load_image_file(file_name + name))[0]
                        known_encodings.append(tmp)
                        names.append(name)
                    except:
                        print("Couldn't find a face for " + name + "!!! Crap...")
        else:
            print("data is not a dictttt")
    else:
        print("NO DATA LOL")


'''
    FUNCTION: starts the stream at the given database location, and handles the stream with the stream_handler function
'''
class FirebaseStreamer(threading.Thread):
   def __init__(self, threadID, ):
      threading.Thread.__init__(self)
      self.threadID = threadID
   def run(self):
      startStream()

def startStream():
    db.child("people/door1").stream(stream_handler)


'''
    FUNCTION: send notifications
'''
class NotificationSender(threading.Thread):
   def __init__(self, threadID, ):
      threading.Thread.__init__(self)
      self.threadID = threadID
   def run(self):
      sendNotifications()

def sendNotifications():
    while True:
        while len(notificationQueue) > 0:
            notification = notificationQueue.pop()
            notification_frame = notification[0]
            notification_name = notification[1]
            notification_key = notification[2]
            save_frame("saved_frames/" + notification_key + ".jpg", notification_frame)
            send_frame_to_database(notification_key, "saved_frames/" + notification_key + ".jpg", notification_name)
            send_FCM_Notification(notification_name)



# start stream on another thread so the camera can run on main thread
firebaseThread = FirebaseStreamer("FirebaseStreamer")
firebaseThread.start()

# thread.start_new_thread(startStream, ())

notificationThread = NotificationSender("NotificationSender")
notificationThread.start()

# # start notification sender on another thread
# thread.start_new_thread(notificationSender, ())


def getColor(name):
    '''
    Return the color of the rectangle to be drawn around a face.
    Unknown should have a red rectangle.
    Known faces should have a green rectangle.
    '''
    if name == "Unknown":
        return(0,0,255)
    else:
        return(0,255,0)


def attemptToOpenDoor(name):
	'''
    Attempt to open door with a name. If name is not unknown, the door should
	open.
    '''
	if name != "Unknown":

	    db.child("doors/door1").update({"status": False, "lastChanged":{".sv": "timestamp"}})

# start the camera stream on the main thread
while True:
    # Grab a single frame of video
    ret, frame = video_capture.read()

    # Resize frame of video to 1/4 size for faster face recognition processing
    small_frame = cv2.resize(frame, (0, 0), fx=1.0/scaling_factor, fy=1.0/scaling_factor)

    # Only process one of every 10 frames of video to save
    if counter % 10 == 0:
        # Find all the faces and face encodings in the current frame of video
        face_locations = face_recognition.face_locations(small_frame)
        face_encodings = face_recognition.face_encodings(small_frame, face_locations)

        face_names = []
        for face_encoding in face_encodings:
            # See if the face is a match for the known face(s)
            match = list(face_recognition.face_distance(known_encodings, face_encoding))
            name = "Unknown"
            best_match_dist = 1
            for i in range(len(match)):
                if match[i] < best_match_dist and match[i] < .55:
                    best_match_dist = match[i]
                    name = names[i]
                    attemptToOpenDoor(name)

            if should_send_notification(name):
                last_sent_notifications[name] = time.time()
                random_key = db.generate_key()
                notificationQueue.append((frame, name, random_key))

            face_names.append(name)
        counter = 0

    counter += 1

    # Display the results
    for (top, right, bottom, left), name in zip(face_locations, face_names):
        # Scale back up face locations since the frame we detected in was scaled
        top *= scaling_factor
        right *= scaling_factor
        bottom *= scaling_factor
        left *= scaling_factor

        # Draw a box around the face
        cv2.rectangle(frame, (left, top), (right, bottom), getColor(name), 2)

        # Draw a label with a name below the face
        cv2.rectangle(frame, (left, bottom - 35), (right, bottom), getColor(name), -1)
        font = cv2.FONT_HERSHEY_DUPLEX
        cv2.putText(frame, name, (left + 6, bottom - 6), font, 1.0, (255, 255, 255), 1)

    # Display the resulting image
    cv2.imshow('Video', frame)


    # Hit 'q' on the keyboard to quit!
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Release handle to the webcam
video_capture.release()
cv2.destroyAllWindows()
