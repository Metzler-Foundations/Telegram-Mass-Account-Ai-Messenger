"""
Location Spoofer - Geographic location simulation for discovery.

Features:
- Randomized location generation
- Major city coordinates
- Location rotation strategies
- Realistic location paths
"""

import random
import math
from typing import Tuple, List
from dataclasses import dataclass


@dataclass
class GeoLocation:
    """Geographic location."""
    latitude: float
    longitude: float
    name: str = ""


class LocationSpoofer:
    """Location spoofing utilities."""
    
    # Major world cities with coordinates
    MAJOR_CITIES = {
        'new_york': (40.7128, -74.0060),
        'london': (51.5074, -0.1278),
        'paris': (48.8566, 2.3522),
        'tokyo': (35.6762, 139.6503),
        'dubai': (25.2048, 55.2708),
        'singapore': (1.3521, 103.8198),
        'hong_kong': (22.3193, 114.1694),
        'sydney': (-33.8688, 151.2093),
        'toronto': (43.6532, -79.3832),
        'los_angeles': (34.0522, -118.2437),
        'chicago': (41.8781, -87.6298),
        'miami': (25.7617, -80.1918),
        'berlin': (52.5200, 13.4050),
        'madrid': (40.4168, -3.7038),
        'rome': (41.9028, 12.4964),
        'moscow': (55.7558, 37.6173),
        'istanbul': (41.0082, 28.9784),
        'mumbai': (19.0760, 72.8777),
        'delhi': (28.7041, 77.1025),
        'bangkok': (13.7563, 100.5018),
        'seoul': (37.5665, 126.9780),
        'beijing': (39.9042, 116.4074),
        'shanghai': (31.2304, 121.4737),
        'sao_paulo': (-23.5505, -46.6333),
        'mexico_city': (19.4326, -99.1332),
    }
    
    @staticmethod
    def get_random_location(base_city: str = None, radius_km: float = 10.0) -> GeoLocation:
        """Get a random location, optionally near a base city.
        
        Args:
            base_city: Base city key (from MAJOR_CITIES)
            radius_km: Radius in km for randomization
            
        Returns:
            GeoLocation object
        """
        if base_city and base_city in LocationSpoofer.MAJOR_CITIES:
            base_lat, base_lon = LocationSpoofer.MAJOR_CITIES[base_city]
            name = base_city.replace('_', ' ').title()
        else:
            # Random city
            city_key = random.choice(list(LocationSpoofer.MAJOR_CITIES.keys()))
            base_lat, base_lon = LocationSpoofer.MAJOR_CITIES[city_key]
            name = city_key.replace('_', ' ').title()
        
        # Add random offset within radius
        lat, lon = LocationSpoofer._add_random_offset(base_lat, base_lon, radius_km)
        
        return GeoLocation(latitude=lat, longitude=lon, name=name)
    
    @staticmethod
    def _add_random_offset(lat: float, lon: float, radius_km: float) -> Tuple[float, float]:
        """Add random offset to coordinates within radius.
        
        Args:
            lat: Base latitude
            lon: Base longitude
            radius_km: Radius in kilometers
            
        Returns:
            (latitude, longitude) tuple
        """
        # Convert radius to degrees (approximate)
        # 1 degree ≈ 111 km
        radius_deg = radius_km / 111.0
        
        # Random angle and distance
        angle = random.uniform(0, 2 * math.pi)
        distance = random.uniform(0, radius_deg)
        
        # Calculate new coordinates
        new_lat = lat + (distance * math.cos(angle))
        new_lon = lon + (distance * math.sin(angle) / math.cos(math.radians(lat)))
        
        # Ensure valid ranges
        new_lat = max(-90, min(90, new_lat))
        new_lon = max(-180, min(180, new_lon))
        
        return new_lat, new_lon
    
    @staticmethod
    def get_location_path(start_city: str, end_city: str, steps: int = 5) -> List[GeoLocation]:
        """Generate a path of locations between two cities.
        
        Args:
            start_city: Starting city key
            end_city: Ending city key
            steps: Number of intermediate steps
            
        Returns:
            List of GeoLocation objects
        """
        if start_city not in LocationSpoofer.MAJOR_CITIES or end_city not in LocationSpoofer.MAJOR_CITIES:
            return []
        
        start_lat, start_lon = LocationSpoofer.MAJOR_CITIES[start_city]
        end_lat, end_lon = LocationSpoofer.MAJOR_CITIES[end_city]
        
        path = []
        for i in range(steps + 1):
            t = i / steps  # Interpolation factor
            lat = start_lat + (end_lat - start_lat) * t
            lon = start_lon + (end_lon - start_lon) * t
            
            # Add small randomization
            lat, lon = LocationSpoofer._add_random_offset(lat, lon, 2.0)
            
            name = f"Step {i+1}/{steps+1}"
            path.append(GeoLocation(latitude=lat, longitude=lon, name=name))
        
        return path
    
    @staticmethod
    def get_nearby_offset(lat: float, lon: float, distance_km: float) -> GeoLocation:
        """Get a nearby location at specific distance.
        
        Args:
            lat: Base latitude
            lon: Base longitude
            distance_km: Distance in km
            
        Returns:
            GeoLocation object
        """
        new_lat, new_lon = LocationSpoofer._add_random_offset(lat, lon, distance_km)
        return GeoLocation(latitude=new_lat, longitude=new_lon, name=f"{distance_km}km offset")
    
    @staticmethod
    def get_all_major_cities() -> List[GeoLocation]:
        """Get all major city locations.
        
        Returns:
            List of GeoLocation objects
        """
        return [
            GeoLocation(lat, lon, name.replace('_', ' ').title())
            for name, (lat, lon) in LocationSpoofer.MAJOR_CITIES.items()
        ]

