from flask import Flask, render_template_string
from flask_socketio import SocketIO, emit
import requests

app = Flask(__name__)
socketio = SocketIO(app)

# OpenCage API Key (Replace with your own API key)
OPENCAGE_API_KEY = 'd0912921b03b43ef94bf5cccb2194195'
OPENCAGE_URL = 'https://api.opencagedata.com/geocode/v1/json'

# In-memory storage for device locations
device_locations = {
    'device1': {'lat': None, 'lon': None},
    'device2': {'lat': None, 'lon': None}
}

# Store bus stops (manually marked)
bus_stops = []

@app.route('/')
def index():
    return render_template_string('''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Real-Time Geolocation Tracking with Bus Stops</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet/dist/leaflet.css" />
    <style>
        #map {
            height: 400px;
            width: 100%;
        }
        #busStopInfo {
            margin-top: 20px;
            font-size: 1.2em;
        }
    </style>
    <script src="https://unpkg.com/leaflet/dist/leaflet.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.0/socket.io.js"></script>
</head>
<body>
    <h1>Real-Time Geolocation Tracking with Bus Stops</h1>
    <button onclick="getLocation()">Start Bus Tracking</button>
    <div id="map"></div>
    <div id="busStopInfo">Bus Stop: Not yet reached</div>

<script>
    let map;
    let sourceMarker;
    let destinationMarker;
    let currentMarker;
    let routingControl;
    const sourceCoords = [11.0835, 76.9966];
    const destinationCoords = [11.4771273, 77.147258];
    const busStops = [];
    const stopMarkers = [];

    const socket = io();

    function initializeMap() {
        map = L.map('map').setView(sourceCoords, 10);

        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        }).addTo(map);

        sourceMarker = L.marker(sourceCoords).addTo(map).bindPopup("Source Location");
        destinationMarker = L.marker(destinationCoords).addTo(map).bindPopup("Destination Location");
        currentMarker = L.marker([0, 0]).addTo(map).bindPopup("Your Current Location");

        map.on('click', function(e) {
            const latLng = e.latlng;
            const stopName = prompt("Enter Bus Stop Name:");
            if (stopName) {
                const stopMarker = L.marker([latLng.lat, latLng.lng]).addTo(map).bindPopup(stopName);
                stopMarkers.push(stopMarker);
                busStops.push({ name: stopName, lat: latLng.lat, lon: latLng.lng });
                socket.emit('add_bus_stop', { name: stopName, lat: latLng.lat, lon: latLng.lng });
            }
        });

        socket.on('update_locations', function(deviceLocations) {
            if (deviceLocations.device2.lat !== null && deviceLocations.device2.lon !== null) {
                const busLatLng = [deviceLocations.device2.lat, deviceLocations.device2.lon];
                currentMarker.setLatLng(busLatLng).setPopupContent("Your Current Location");

                updateBusStopInfo(busLatLng);
            }
        });
    }

    function updateBusStopInfo(busLatLng) {
        const thresholdDistance = 0.5; // 500 meters
        let closestStop = null;
        let minDistance = thresholdDistance;

        busStops.forEach(stop => {
            const distance = calculateDistance(busLatLng, [stop.lat, stop.lon]);
            if (distance < minDistance) {
                minDistance = distance;
                closestStop = stop;
            }
        });

        if (closestStop) {
            document.getElementById('busStopInfo').innerText = `Bus Stop: ${closestStop.name}`;
        } else {
            document.getElementById('busStopInfo').innerText = `Bus Stop: Not yet reached`;
        }
    }

    function getLocation() {
        if (navigator.geolocation) {
            navigator.geolocation.watchPosition(
                (position) => sendLocationToServer(position),
                showError,
                {
                    enableHighAccuracy: true,
                    maximumAge: 0,
                    timeout: 5000
                }
            );
        } else {
            alert("Geolocation is not supported by this browser.");
        }
    }

    function sendLocationToServer(position) {
        const latitude = position.coords.latitude;
        const longitude = position.coords.longitude;

        socket.emit('send_location', {
            lat: latitude,
            lon: longitude,
            deviceId: 'device2'
        });
    }

    function calculateDistance(coord1, coord2) {
        const R = 6371; // Radius of the Earth in kilometers
        const lat1 = coord1[0] * Math.PI / 180;
        const lon1 = coord1[1] * Math.PI / 180;
        const lat2 = coord2[0] * Math.PI / 180;
        const lon2 = coord2[1] * Math.PI / 180;

        const dLat = lat2 - lat1;
        const dLon = lon2 - lon1;

        const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
                  Math.cos(lat1) * Math.cos(lat2) *
                  Math.sin(dLon / 2) * Math.sin(dLon / 2);
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
        const distance = R * c;

        return distance;
    }

    function showError(error) {
        switch (error.code) {
            case error.PERMISSION_DENIED:
                alert("User denied the request for Geolocation.");
                break;
            case error.POSITION_UNAVAILABLE:
                alert("Location information is unavailable.");
                break;
            case error.TIMEOUT:
                alert("The request to get user location timed out.");
                break;
            case error.UNKNOWN_ERROR:
                alert("An unknown error occurred.");
                break;
        }
    }

    window.onload = initializeMap;
    getLocation();
</script>
</body>
</html>
''')

@socketio.on('send_location')
def handle_location(data):
    device_id = data['deviceId']
    latitude = data['lat']
    longitude = data['lon']
   
    if device_id in device_locations:
        device_locations[device_id]['lat'] = latitude
        device_locations[device_id]['lon'] = longitude
        emit('update_locations', device_locations, broadcast=True)
    else:
        emit('error', {'message': 'Invalid device ID'}) 

@socketio.on('add_bus_stop')
def add_bus_stop(data):
    bus_stops.append(data)
    print(f"Added bus stop: {data['name']} at ({data['lat']}, {data['lon']})")

def reverse_geocode(lat, lon):
    params = {
        'key': OPENCAGE_API_KEY,
        'q': f'{lat},{lon}',
        'pretty': 1
    }
    response = requests.get(OPENCAGE_URL, params=params)
    data = response.json()
    if data['results']:
        return data['results'][0]['formatted']
    else:
        return "Address not found"

if __name__ == '__main__':
    socketio.run(app, debug=True)
