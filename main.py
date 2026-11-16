import requests
from datetime import datetime as dt
from drafter import *
from bakery import assert_equal
from dataclasses import dataclass
import math
import sys


@dataclass
class State:
    point_time_weather_list: list[PointTimeWeather]
    flight_data: FlightData
    departing_airport: Airport
    valid_dpt: False
    arriving_airport: Airport
    valid_arr: False
    

@dataclass
class FlightData:
    departing_time: int
    time_of_flight: int
    probing_points: int


@dataclass
class PointTimeWeather:
    visibility: float
    wind_speed: float
    cloud_cover: int
    lat: float
    long: float
    

@dataclass
class Airport:
    code: str
    lat: float
    long: float
    

def iso_to_unix_list(iso_list: list[str]) -> list[int]:
    """
    Transforms an ISO formatted datetime into a Unix timestamp (seconds).
    
    Args:
        iso_list (list[str]): A list of all the ISO times to be converted.
    Returns:
        list[int]: A list of the converted Unix times.
    """
    unix_list = []
    for iso_datetime in iso_list:
        unix_list.append(int(dt.fromisoformat(iso_datetime).timestamp()))
    return unix_list


def create_flight_data(dep_hrs: int, dep_mins: int, tof_hrs: int, tof_mins: int, probing_points: int) -> FlightData:
    """
    Initializes the FlightData dataclass from information submitted here.
    
    Args:
        dep_hrs (int): The hours of departure.
        dep_mins (int): The minutes of departure.
        tof_hrs (int): The hours of flight time.
        tof_mins (int): The minutes of flight time.
    Returns:
        The initialized FlightData dataclass object.
    """
    now = dt.now()
    departure = dt(now.year, now.month, now.day, dep_hrs, dep_mins).timestamp()
    flight_time = (tof_hrs * 3600) + (tof_mins * 60)
    
    return FlightData(departure, flight_time, probing_points)


def get_weather_at_point_time(lat: float, long: float, time: int) -> list:
    minutely_15_point_time = round(time / 900) * 900
    hourly_point_time = round(time / 3600) * 3600
    
    weather_url = ('https://api.open-meteo.com/v1/forecast?latitude=' + str(lat) +
                   '&longitude=' + str(long) +
                   '&hourly=cloud_cover_low&models=ncep_gfs_seamless&minutely_15=visibility,wind_speed_80m&forecast_days=2&timezone=America/New_York'
                   )
    raw_weather_data = requests.get(weather_url).json()
    
    minutely_15 = iso_to_unix_list(raw_weather_data['minutely_15']['time'])
    hourly = iso_to_unix_list(raw_weather_data['hourly']['time'])
    
    minutely_15_index = minutely_15.index(minutely_15_point_time)
    hourly_index = hourly.index(hourly_point_time)
    
    visibility = raw_weather_data['minutely_15']['visibility'][minutely_15_index]
    wind_speed = raw_weather_data['minutely_15']['wind_speed_80m'][minutely_15_index]
    cloud_cover = raw_weather_data['hourly']['cloud_cover_low'][hourly_index]
    
    return PointTimeWeather(visibility, wind_speed, cloud_cover, lat, long)


def get_airport(query: str) -> Airport:
    airport_url = 'https://airportsapi.com/api/airports/' + query
    raw_airport_data = requests.get(airport_url).json()
    airport_attributes = raw_airport_data['data']['attributes']
    
    code = airport_attributes['icao_code']
    lat = airport_attributes['latitude']
    long = airport_attributes['longitude']
    
    return Airport(code, lat, long)


def get_weathers_between_airports(first_ap: Airport, second_ap: Airport, flight_data: FlightData) -> list[PointTimeWeather]:
    lat_difference = first_ap.lat - second_ap.lat
    long_difference = first_ap.long - second_ap.long

    weather_list = []
    for point_index in range(flight_data.probing_points):
        point_lat = first_ap.lat - ((lat_difference / 10) * point_index)
        point_long = first_ap.long - ((long_difference / 10) * point_index)
        time_at_point = flight_data.departing_time + ((flight_data.time_of_flight / 10) * point_index)
        
        point_weather = get_weather_at_point_time(point_lat, point_long, time_at_point)
        weather_list.append(point_weather)
        
    return weather_list


@route
def index(state: State) -> Page:
    return Page(state, [
        Header("Should I Fly Today?"),
        "This program will search the route between two airports and find if it is safe to fly that day based on weather.\n",
        Button("Begin", "select_airports"),
        Button("More Info", "more_info")
    ])


@route
def more_info(state: State) -> Page:
    return Page(state, [
        Header("More Information"),
        "This program is useful when attempting to see if weather is good to fly during the time specified by the user.\n",
        "It saves considerable amounts of time, especially if it is clearly not a good day to fly, but you must check.\n",
        "Regardless of what this program says, the user must STILL manually verify the weather if they plan to fly.\n",
        "However, this program will tell you before you research if you shouldn't even consider it!",
        "If you need to find airport codes to use, visit ",
        Link("this page.", "https://www.flightaware.com/resources/airport/browse/PA"), "\n",
        Button("Go Back", "index")
    ])


@route
def select_airports(state: State) -> Page:
    return Page(state, [
        Header("Pick Your Airports!"),
        TextBox("first_ap"),
        TextBox("second_ap"),
        "The button below will not work until both airport inputs are valid.",
        Button("Continue to Flight Data Collection", "check_valid_airport")
    ])

@route
def check_valid_airport(state: State, first_ap: str, second_ap: str):
    if first_ap:
        response = requests.get('https://airportsapi.com/api/airports/' + first_ap)
        if response.status_code != 404:
            state.departing_airport = get_airport(first_ap)
            state.valid_dpt = True
    if second_ap:
        response = requests.get('https://airportsapi.com/api/airports/' + second_ap)
        if response.status_code != 404:
            state.arriving_airport = get_airport(second_ap)
            state.valid_arr = True
    print(state)
    if state.valid_arr and state.valid_dpt:
        return get_flight_data(state)
    else:
        return select_airports(state)


@route
def get_flight_data(state: State) -> Page:
    return Page(state, [ 
        Header("Input Flight Data"),
        "Input what time you are leaving in hour/minute format.",
        TextBox("dep_hrs"), TextBox("dep_mins"), "\n",
        "Input how long the flight will be in hour/minute format.",
        TextBox("tof_hrs"), TextBox("tof_mins"),
        "\nThe map will not display if all boxes are not filled.\n",
        Button("Continue to the Map", "generate_map")
    ])
    
    
@route
def generate_map(state:State, dep_hrs: int, dep_mins: int, tof_hrs: int, tof_mins: int) -> Page:
    """
    Probes are locked to 10 at the moment; there are a max of 10000 requests per day from one IP.
    """
    if not dep_hrs and dep_mins and tof_hrs and tof_mins:
        return get_flight_data(state)
    state.flight_data = create_flight_data(dep_hrs, dep_mins, tof_hrs, tof_mins, 10)
    state.point_time_weather_list = get_weathers_between_airports(state.departing_airport, state.arriving_airport,
                                                                  state.flight_data)
    return display_map(state)
    


@route
def display_map(state: State) -> Page:
    center_lat = ((state.departing_airport.lat - state.arriving_airport.lat) / 2) + state.departing_airport.lat
    center_long = ((state.departing_airport.long - state.arriving_airport.long) / 2) + state.departing_airport.long
    marker_list = []
    for weather_point in state.point_time_weather_list:
        label = ("Visibility: " + str(weather_point.visibility)
                 + "\nWind Speed: " + str(weather_point.wind_speed)
                 + "\nCloud Cover: " + str(weather_point.cloud_cover))
        marker_list.append(MapMarker(weather_point.lat, weather_point.long, label))

    return Page(state, [
        Map("flight_map_points", center=MapLocation(center_lat, center_long),
            zoom=5, markers=marker_list, on_marker_click=None, on_move=None),
        Button("Continue to Weather Results", "weather_results")
        ])


@route
def weather_results(state: State) -> Page:
    statement = "It is NOT advisable to fly today."
    points = 30
    for weather_point in state.point_time_weather_list:
        if weather_point.visibility <= 5000.0:
            points -= 1
        if weather_point.wind_speed <= 30.0:
            points -= 1
        if weather_point.cloud_cover <= 50:
            points -= 1
    if points >= 23:
        statement = "It MAY be advisable to fly today."
    return Page(state, [
        Header("Weather Results"),
        "The number of points checked along the route is limited to 10 for ratelimit purposes.\n",
        "Each point has 3 values: visibility, cloud cover, and wind.\n",
        "VFR flights are considered unsafe or advised against when they exceed published maximums.\n",
        "This occurs when either cloud cover is above 50 percent, wind is greater than 30 knots,",
        "or visibility is less than 5km. There are 30 total values to check from the 10 points.\n",
        "A flight is not viable to continue and research when less than 75% of the values are valid.\n\n\n",
        Header(statement, 1),
        "\nTotal value score: " + str(points) + "/30.",
        Button("Back to Home", index)
    ])
    

start_server(State(None, None, None, None, None, None))
