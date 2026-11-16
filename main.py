import requests
from datetime import datetime as dt
from drafter import *
from bakery import assert_equal
from dataclasses import dataclass
import math
import sys


set_website_title("Flight Checker")

set_site_information(
    author="Noah Hover",
    description="A VFR weather planner that checks forecast conditions between two airports.",
    sources="Drafter documentation and StackOverflow.",
    #plan.pdf
    planning="",
    links=["https://github.com/notabrit/flight-checker"]
)
hide_debug_information()
set_website_framed(False)
    

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
    
    
@dataclass
class State:
    point_time_weather_list: list[PointTimeWeather]
    flight_data: FlightData
    departing_airport: Airport
    valid_dpt: bool
    arriving_airport: Airport
    valid_arr: bool
    

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


assert_equal(iso_to_unix_list([]), [])
assert_equal(iso_to_unix_list(["1970-01-01T00:00:00+00:00"]), [0])
assert_equal(iso_to_unix_list(["1970-01-01T00:15:00+00:00"]), [900])
assert_equal(iso_to_unix_list(["1970-01-01T01:00:00+00:00"]), [3600])


def create_flight_data(dep_hrs: int, dep_mins: int, tof_hrs: int, tof_mins: int, probing_points: int) -> FlightData:
    """
    Initializes the FlightData dataclass from information submitted here.
    
    Args:
        dep_hrs (int): The hours of departure.
        dep_mins (int): The minutes of departure.
        tof_hrs (int): The hours of flight time.
        tof_mins (int): The minutes of flight time.
        probing_points (int): The number of probe points, or lat/long/time to check, across the entire route.
    Returns:
        FlightData: The initialized FlightData dataclass object.
    """
    now = dt.now()
    departure = dt(now.year, now.month, now.day, dep_hrs, dep_mins).timestamp()
    flight_time = (tof_hrs * 3600) + (tof_mins * 60)
    
    return FlightData(departure, flight_time, probing_points)


assert_equal(create_flight_data(14, 30, 1, 45, 10).time_of_flight, 6300)
assert_equal(create_flight_data(9, 15, 2, 30, 5).time_of_flight, 9000)
assert_equal(create_flight_data(9, 15, 2, 30, 5).probing_points, 5)
assert_equal(create_flight_data(14, 30, 1, 45, 10).probing_points, 10)
assert_equal(dt.fromtimestamp(create_flight_data(14, 30, 1, 45, 10).departing_time).hour, 14)
assert_equal(dt.fromtimestamp(create_flight_data(14, 30, 1, 45, 10).departing_time).minute, 30)


def get_weather_at_point_time(lat: float, long: float, time: int) -> PointTimeWeather:
    """
    Fetches raw weather data at a specific lat/long pair and a specific time from a free endpoint.
    Returns a PointTimeWeather dataclass object with all information and location.
    The raw data is turned from JSON to a Dictionary using the requests module.
    The Unix timestamp provided by the user is rounded to the nearest 15 minute and hourly interval.
    This is because weather radar is only updated once per 15 minutes or per hour, depending on the variable.
    This function cannot be unit tested as it returns live data.
    
    Args:
        lat (float): The latitude of the point.
        long (float): The longitude of the point.
        time (int): The Unix timestamp of when to sample the weather data.
    Returns:
        PointTimeWeather: The constructed dataclass with the location of the point and the weather variables attached.
    """
    minutely_15_point_time = round(time / 900) * 900
    hourly_point_time = round(time / 3600) * 3600
    
    weather_url = ('https://api.open-meteo.com/v1/forecast?latitude=' + str(lat) +
                   '&longitude=' + str(long) +
                   '&hourly=cloud_cover_low&models=ncep_gfs_seamless' +
                   '&minutely_15=visibility,wind_speed_80m&forecast_days=2&timezone=America/New_York'
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
    """
    Fetches raw airport data from a string query provided by the user.
    Constructs an Airport dataclass object with it's lat/long pair and 'K' code.
    This function cannot be unit tested as it returns live data.
    
    Args:
        query (str): The query of the airport name to fetch.
    Returns:
        Airport: An airport object with a lat/long pair and 'K' code attached.
    """
    airport_url = 'https://airportsapi.com/api/airports/' + query
    raw_airport_data = requests.get(airport_url).json()
    airport_attributes = raw_airport_data['data']['attributes']
    
    code = airport_attributes['icao_code']
    lat = airport_attributes['latitude']
    long = airport_attributes['longitude']
    
    return Airport(code, lat, long)


def get_weathers_between_airports(first_ap: Airport, second_ap: Airport,
                                  flight_data: FlightData) -> list[PointTimeWeather]:
    """
    Gets the weather at 10 points equidistant in position and time between the two airports provided by the user.
    The weather is appeneded to a list and returned.
    This function cannot be unit tested as it returns live data.
    
    Args:
        first_ap (Airport): The departing airport.
        second_ap (Airport): The arriving airport.
    Returns:
        list[PointTimeWeather]: A list of weather points at their respective times.
    """
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
    """
    The home page of the prgoram.
    The only interactable elements here are two buttons to continue to More Info, or to continue to Select Airports.
    This function has no logic to be unit tested.
    
    Args:
        state (State): The drafter state.
    Returns:
        Page: The Home page.
    """
    return Page(state, [
        Header("Should I Fly Today?"),
        "This program will search the route between two airports and find if ",
        "it is safe to fly that day based on weather.\n",
        Button("Begin", "select_airports"),
        Button("More Info", "more_info")
    ])


@route
def more_info(state: State) -> Page:
    """
    More info about the project.
    The only interactable element here is a button to go back to the Home page.
    This function has no logic to be unit tested.
    
    Args:
        state (State): The drafter state.
    Returns:
        Page: The More Info page.
    """
    return Page(state, [
        Header("More Information"),
        "This program is useful when attempting to see if weather is ",
        "good to fly during the time specified by the user.\n",
        "It saves considerable amounts of time, especially if it is ",
        "clearly not a good day to fly, but you must check.\n",
        "Regardless of what this program says, the user must STILL manually verify the weather if they plan to fly.\n",
        "However, this program will tell you before you research if you shouldn't even consider it!",
        "If you need to find airport codes to use, visit ",
        Link("this page.", "https://www.flightaware.com/resources/airport/browse/PA"), "\n",
        Button("Go Back", "index")
    ])


@route
def select_airports(state: State) -> Page:
    """
    Gets the airports from the user. There is no logic here; it is handled in check_valid_airport.
    This function has not logic to be unit tested.
    
    Args:
        state (State): The drafter state.
    Returns:
        Page: The page to collect the airport data.
    """
    
    return Page(state, [
        Header("Pick Your Airports!"),
        TextBox("first_ap"), "\n",
        TextBox("second_ap"), "\n",
        "The button below will not work until both airport inputs are valid.\n",
        Button("Continue to Flight Data Collection", "check_valid_airport")
    ])


def check_valid(state: State, first_ap: str, second_ap: str) -> State:
    """
    Determines if the airports provided are valid and real.
    If not, the state will not change.
    Otherwise, the airports (using the get_airport() function) will be attached to the state and returned.
    
    Args:
        state (State): The drafter state.
        first_ap (str): The departing airport.
        second_ap (str): The arriving airport.
    Returns:
        State: The modified state.
    """
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
    return state


assert_equal(
    check_valid(State([], None, None, False, None, False), "", ""),
    State([], None, None, False, None, False)
)

assert_equal(
    check_valid(State([], None, Airport("KABE", 40.65, -75.44), True, None, False), "", ""),
    State([], None, Airport("KABE", 40.65, -75.44), True, None, False)
)


@route
def check_valid_airport(state: State, first_ap: str, second_ap: str) -> Page:
    """
    Determines if the airports provided are valid and rea using the check_valid function.
    The only logic this function uses is an if statement; all else is handled by the helper.
    Otherwise, the asserts here would be the size of almost a third of the entire program.
    
    Args:
        state (State): The drafter state.
        first_ap (Airport): The departing airport.
        second_ap (Airport): The arriving airport.
    Returns:
        Page: Either the previous page if state is unchanged, or the next Select Airports page.
    """
    
    state = check_valid(state, first_ap, second_ap)

    if state.valid_arr and state.valid_dpt:
        return get_flight_data(state)
    else:
        return select_airports(state)


@route
def get_flight_data(state: State) -> Page:
    """
    Gets the flight data from the user. There is no logic here; it is handled in generate_map.
    This function has no logic to be unit tested.
    
    Args:
        state (State): The drafter state.
    Returns:
        Page: The flight data collection page.
    """
    return Page(state, [ 
        Header("Input Flight Data"),
        "Input what time you are leaving in hour/minute format.\n",
        TextBox("dep_hrs"), TextBox("dep_mins"), "\n",
        "Input how long the flight will be in hour/minute format.\n",
        TextBox("tof_hrs"), TextBox("tof_mins"),
        "\nThe map will not display if all boxes are not filled.\n",
        Button("Continue to the Map", "generate_map")
    ])
    
    
@route
def generate_map(state:State, dep_hrs: int, dep_mins: int, tof_hrs: int, tof_mins: int) -> Page:
    """
    Gets the point/time weather list, and creates flight data for the map generation.
    Probes are locked to 10 at the moment; there are a max of 10000 requests per day from one IP.
    
    Args:
        dep_hrs (int): The hour the flight departs.
        dep_mins (int): The minutes the flight departs.
        tof_hrs (int): The hours of flight time.
        tof_mins (int): The minutes of flight time.
    Returns:
        Page: Either the previous drafter page if the fields are incorrect, or the next Flight Data page.
    """

    if not (dep_hrs < 0 or dep_hrs > 24 or dep_mins < 0 or dep_mins > 60 or tof_hrs < 0 or tof_mins < 0 or tof_mins > 60):
        state.flight_data = create_flight_data(dep_hrs, dep_mins, tof_hrs, tof_mins, 10)
        state.point_time_weather_list = get_weathers_between_airports(state.departing_airport, state.arriving_airport,
                                                                      state.flight_data)
        return display_map(state)
        
    return get_flight_data(state)
    
    
assert_equal(
    generate_map(State([], None, None, False, None, False), -1, 30, 1, 0),
    get_flight_data(State([], None, None, False, None, False))
)
assert_equal(
    generate_map(State([], None, None, False, None, False), 25, 0, 1, 0),
    get_flight_data(State([], None, None, False, None, False))
)
assert_equal(
    generate_map(State([], None, None, False, None, False), 12, 70, 1, 0),
    get_flight_data(State([], None, None, False, None, False))
)
assert_equal(
    generate_map(State([], None, None, False, None, False), 12, 30, -1, 0),
    get_flight_data(State([], None, None, False, None, False))
)
assert_equal(
    generate_map(State([], None, None, False, None, False), 12, 30, 1, 70),
    get_flight_data(State([], None, None, False, None, False))
)


@route
def display_map(state: State) -> Page:
    """
    Gets the center between the two airports and the markers from the weather points, and generates a map display.
    This function is difficult to unit test, as the resulting assert_equal is over 100 lines long.
    The logic has been tested seperately.
    
    Args:
        state (State): The drafter state.
    Returns:
        Page: The map page.
    """
    center_lat = state.departing_airport.lat - ((state.departing_airport.lat - state.arriving_airport.lat) / 2)
    center_long = state.departing_airport.long - ((state.departing_airport.long - state.arriving_airport.long) / 2)
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
    """
    Tells the user whether it's probably a good idea to fly today.
    The actual logic is explained to the user.
    
    Args:
        state (State): The drafter state.
    Returns:
        Page: The final drafter page with the weather results.
    """
    statement = "It is NOT advisable to fly today."
    points = 30
    for weather_point in state.point_time_weather_list:
        if weather_point.visibility <= 5000.0:
            points -= 1
        if weather_point.wind_speed >= 30.0:
            points -= 1
        if weather_point.cloud_cover >= 50:
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


assert_equal(
    # Utilizes .content[] of the page which we did not discuss; avoids having 40 lines of asserts here
    weather_results(State(
        [PointTimeWeather(10000.0, 10.0, 20, 40.0, -75.0) for i in range(10)], None, None, False, None, False
    )).content[-2],
    "\nTotal value score: 30/30."
)

assert_equal(
    weather_results(State(
        [PointTimeWeather(1000.0, 40.0, 90, 40.0, -75.0) for i in range(10)], None, None, False, None, False
    )).content[-2],
    "\nTotal value score: 0/30."
)
    

start_server(State(None, None, None, None, None, None))
