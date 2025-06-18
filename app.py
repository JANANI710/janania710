import streamlit as st
from twilio.rest import Client
import geocoder  # To get the user's location
import cv2
import os
import pandas as pd
from datetime import datetime, timedelta
import requests
import folium
from streamlit_folium import folium_static
import openrouteservice  # For decoding the polyline returned by ORS

# ORS API key and destination (Francis Xavier Engineering College, Tirunelveli)
ORS_API_KEY = '5b3ce3597851110001cf624881e627ff65644952b177da2af87ab047'
DEST_LAT = 8.7244041
DEST_LON = 77.7350118

# Twilio credentials
TWILIO_SID = "AC4247e18c46ef8461f450002781c0a6ca"
TWILIO_TOKEN = "2f4480fd80ac76030deb40fec6f67ae9"
TWILIO_PHONE = "+19407481203"

# Directory to save videos and photos
SAVE_DIR = "saved_videos"
PHOTO_DIR = "saved_photos"

# Ensure directories exist
os.makedirs(SAVE_DIR, exist_ok=True)
os.makedirs(PHOTO_DIR, exist_ok=True)

# Function to make SOS call
def make_sos_call(emergency_contact):
    try:
        client = Client(TWILIO_SID, TWILIO_TOKEN)
        call = client.calls.create(
            url="http://demo.twilio.com/docs/voice.xml",
            to=emergency_contact,
            from_=TWILIO_PHONE
        )
        st.success("🚨 SOS call initiated!")
    except Exception as e:
        st.error(f"❌ Failed to make SOS call: {str(e)}")

# Function to share location via SMS
def share_location(emergency_contact):
    try:
        g = geocoder.ip('me')
        location = g.latlng
        if location:
            client = Client(TWILIO_SID, TWILIO_TOKEN)
            message = f"🔴 Help needed! My location: https://www.google.com/maps?q={location[0]},{location[1]}"
            client.messages.create(body=message, from_=TWILIO_PHONE, to=emergency_contact)
            st.success("📍 Location shared via SMS!")
        else:
            st.error("❌ Could not retrieve location.")
    except Exception as e:
        st.error(f"❌ Failed to share location: {str(e)}")

# Function to capture video and detect face
def capture_video_with_face_detection():
    video_filename = f"video_{datetime.now().strftime('%Y%m%d_%H%M%S')}.avi"
    video_path = os.path.join(SAVE_DIR, video_filename)

    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    cap = cv2.VideoCapture(0)
    out = cv2.VideoWriter(video_path, cv2.VideoWriter_fourcc(*'XVID'), 20.0, (640, 480))
    st_frame = st.empty()
    start_time = datetime.now()
    photo_taken = False

    while (datetime.now() - start_time) < timedelta(minutes=1):
        ret, frame = cap.read()
        if ret:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray, 1.3, 5)
            for (x, y, w, h) in faces:
                cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 0, 0), 2)
                if not photo_taken:
                    photo_path = os.path.join(PHOTO_DIR, f"photo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg")
                    cv2.imwrite(photo_path, frame[y:y+h, x:x+w])
                    photo_taken = True
            out.write(frame)
            st_frame.image(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), channels='RGB')
    
    cap.release()
    out.release()
    return video_path, photo_path if photo_taken else None

# Function to log emergency data
def log_data(emergency_contact, video_path, photo_path):
    df = pd.DataFrame({
        'Timestamp': [datetime.now()],
        'Emergency Contact': [emergency_contact],
        'Video Path': [video_path],
        'Photo Path': [photo_path]
    })
    file_path = 'emergency_log.xlsx'
    if os.path.exists(file_path):
        existing_df = pd.read_excel(file_path)
        df = pd.concat([existing_df, df], ignore_index=True)
    df.to_excel(file_path, index=False)

# Function to get the safest route
def get_safest_route():
    g = geocoder.ip('me')
    current_location = g.latlng
    if current_location:
        url = "https://api.openrouteservice.org/v2/directions/foot-walking"
        headers = {'Authorization': ORS_API_KEY, 'Content-Type': 'application/json'}
        body = {"coordinates": [[current_location[1], current_location[0]], [DEST_LON, DEST_LAT]], "instructions": True}
        response = requests.post(url, json=body, headers=headers)
        if response.status_code == 200:
            route_data = response.json()
            geometry = route_data['routes'][0]['geometry']
            decoded_geometry = openrouteservice.convert.decode_polyline(geometry)
            return current_location, {"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": {"type": "LineString", "coordinates": decoded_geometry['coordinates']}, "properties": {}}]}
        else:
            st.error(f"ORS Error: {response.status_code}")
    else:
        st.error("❌ Could not retrieve current location.")
    return None, None

# Main Streamlit application
def main():
    st.set_page_config(page_title="Women's Safety App", page_icon="🛡️", layout="wide")
    st.title("🛡️ Women's Safety App")
    st.markdown("### Empowering Women with Safety Tools")
    
    emergency_contact = st.text_input("Emergency Contact Phone Number", "+918778735205")
    if st.button("Trigger Panic Alert"):
        if emergency_contact:
            make_sos_call(emergency_contact)
            share_location(emergency_contact)
            video_path, photo_path = capture_video_with_face_detection()
            log_data(emergency_contact, video_path, photo_path)
            st.success("🚨 Emergency alert triggered successfully!")
    
    st.subheader("Safe Route to Francis Xavier Engineering College")
    current_location, route_geojson = get_safest_route()
    if current_location and route_geojson:
        m = folium.Map(location=current_location, zoom_start=14)
        folium.Marker(location=current_location, popup="Current Location", icon=folium.Icon(color="blue")).add_to(m)
        folium.Marker(location=[DEST_LAT, DEST_LON], popup="Francis Xavier Engineering College", icon=folium.Icon(color="green")).add_to(m)
        folium.GeoJson(route_geojson).add_to(m)
        folium_static(m)

if __name__ == '__main__':
    main()
