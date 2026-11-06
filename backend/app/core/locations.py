"""Built-in location gazetteer (offline, no paid geocoding API).

Users pick source / destination from this list or enter custom coordinates.
"""
LOCATIONS = [
    # India
    {"name": "Hyderabad, IN", "lat": 17.3850, "lon": 78.4867},
    {"name": "Mumbai, IN", "lat": 19.0760, "lon": 72.8777},
    {"name": "Delhi, IN", "lat": 28.6139, "lon": 77.2090},
    {"name": "Bengaluru, IN", "lat": 12.9716, "lon": 77.5946},
    {"name": "Chennai, IN", "lat": 13.0827, "lon": 80.2707},
    {"name": "Kolkata, IN", "lat": 22.5726, "lon": 88.3639},
    {"name": "Pune, IN", "lat": 18.5204, "lon": 73.8567},
    {"name": "Ahmedabad, IN", "lat": 23.0225, "lon": 72.5714},
    {"name": "Jaipur, IN", "lat": 26.9124, "lon": 75.7873},
    {"name": "Lucknow, IN", "lat": 26.8467, "lon": 80.9462},
    {"name": "Nagpur, IN", "lat": 21.1458, "lon": 79.0882},
    {"name": "Visakhapatnam, IN", "lat": 17.6868, "lon": 83.2185},
    {"name": "Vijayawada, IN", "lat": 16.5062, "lon": 80.6480},
    {"name": "Kochi, IN", "lat": 9.9312, "lon": 76.2673},
    {"name": "Coimbatore, IN", "lat": 11.0168, "lon": 76.9558},
    {"name": "Indore, IN", "lat": 22.7196, "lon": 75.8577},
    {"name": "Bhubaneswar, IN", "lat": 20.2961, "lon": 85.8245},
    {"name": "Guwahati, IN", "lat": 26.1445, "lon": 91.7362},
    {"name": "Chandigarh, IN", "lat": 30.7333, "lon": 76.7794},
    {"name": "Nashik, IN", "lat": 19.9975, "lon": 73.7898},
    {"name": "Ooty, IN", "lat": 11.4102, "lon": 76.6950},
    {"name": "Anand, IN", "lat": 22.5645, "lon": 72.9289},
    # International hubs
    {"name": "Dubai, AE", "lat": 25.2048, "lon": 55.2708},
    {"name": "Singapore, SG", "lat": 1.3521, "lon": 103.8198},
    {"name": "Colombo, LK", "lat": 6.9271, "lon": 79.8612},
    {"name": "Dhaka, BD", "lat": 23.8103, "lon": 90.4125},
    {"name": "Kathmandu, NP", "lat": 27.7172, "lon": 85.3240},
    {"name": "Amsterdam, NL", "lat": 52.3676, "lon": 4.9041},
    {"name": "Frankfurt, DE", "lat": 50.1109, "lon": 8.6821},
    {"name": "London, GB", "lat": 51.5072, "lon": -0.1276},
    {"name": "Nairobi, KE", "lat": -1.2921, "lon": 36.8219},
    {"name": "New York, US", "lat": 40.7128, "lon": -74.0060},
]

