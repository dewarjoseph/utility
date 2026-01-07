import random
from analyzer import Property

ADDRESS_STREETS = ["Pacific Ave", "Mission St", "Ocean St", "Soquel Ave", "Broadway", "Seabright Ave", "Bay St", "High St", "Cliff Dr", "Empire Grade"]
ZONES = ["R-1", "M-1", "A-1", "C-3", "R-M"]

def generate_mock_data(count=100) -> list[Property]:
    properties = []
    
    for i in range(count):
        zoning = random.choice(ZONES)
        
        # Correlation: Mountain addresses (Empire Grade) have higher slopes
        street = random.choice(ADDRESS_STREETS)
        is_mountain = street in ["Empire Grade", "High St"]
        
        if is_mountain:
            slope = random.uniform(15.0, 60.0)
            acres = random.uniform(2.0, 40.0)
            dist_water = random.uniform(500, 5000)
            coastal = False
        elif street == "Cliff Dr":
            slope = random.uniform(0.0, 15.0)
            acres = random.uniform(0.1, 1.0)
            dist_water = random.uniform(10, 200)
            coastal = True
        else:
            slope = random.uniform(0.0, 10.0)
            acres = random.uniform(0.1, 5.0)
            dist_water = random.uniform(50, 1000)
            coastal = random.choice([True, False])

        # Generate a "Listing Description" for the Vector Search
        desc_parts = []
        if zoning == "M-1": desc_parts.append("Industrial zoned lot.")
        if zoning == "R-1": desc_parts.append("Residential parcel.")
        if zoning == "A-1": desc_parts.append("Agricultural land.")
        
        if slope < 5: desc_parts.append("Flat and ready to build.")
        elif slope > 30: desc_parts.append("Steep terrain with views.")
        
        if dist_water < 200: desc_parts.append("Has water access nearby.")
        if coastal: desc_parts.append("Ocean views / Coastal zone.")
        
        description = f"Lot on {street}. {' '.join(desc_parts)}"

        prop = Property(
            id=f"PROP-{i:03d}-{street.replace(' ', '')}",
            acres=round(acres, 2),
            zoning=zoning,
            slope_percent=round(slope, 1),
            distance_to_water_source_ft=round(dist_water, 1),
            solar_exposure_score=round(random.uniform(0.5, 1.0), 2),
            in_coastal_zone=coastal,
            flood_risk_zone=(random.random() < 0.1),
            description=description
        )
        properties.append(prop)
        
    return properties
