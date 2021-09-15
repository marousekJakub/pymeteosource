"""Tests for pymeteosource"""

import os
import sys
from datetime import datetime
from unittest.mock import MagicMock
from os.path import realpath, join, dirname
import pytz
import pytest
import pandas

from pymeteosource.api import MeteoSource
from pymeteosource.types import tiers, endpoints, units, sections
from pymeteosource.data import Forecast, SingleTimeData, MultipleTimesData
from pymeteosource.types.time_formats import F1
from pymeteosource.errors import (InvalidArgumentError, InvalidIndexType,
                                  InvalidDatetimeIndex, InvalidStrIndex)

from .sample_data import SAMPLE_DATA
from .variables_list import (CURRENT, PRECIPITATION_CURRENT, WIND, MINUTELY,
                             HOURLY, CLOUD, PRECIPITATION, PROBABILITY, DAILY,
                             ALL_DAY, PART_DAY, ASTRO, SUN, MOON, STATS,
                             STATS_TEMP, STATS_WIND, STATS_PREC)

sys.path.insert(0, realpath(join(dirname(__file__), "..")))

# Load API key from environment variable
API_KEY = os.environ.get('METEOSOURCE_API_KEY')
if API_KEY is None:
    raise ValueError("You need to provide API key as environment variable.")


def test_build_url():
    """Test URL building"""
    url = 'https://www.meteosource.com/api/v1/TIER/point'
    for tier in [tiers.PREMIUM, tiers.STANDARD, tiers.STARTUP, tiers.FREE]:
        m = MeteoSource(API_KEY, tier)
        assert m.build_url(endpoints.POINT) == url.replace('TIER', tier)


def test_get_point_forecast_exceptions():
    """Test detection of invalid point specification detection"""
    m = MeteoSource(API_KEY, tiers.PREMIUM)
    # We mock the API requests with sample data
    m.req_handler.execute_request = MagicMock(return_value=SAMPLE_DATA)

    # Test invalid place definitions
    with pytest.raises(InvalidArgumentError) as e:
        m.get_point_forecast(place_id='london', lat=50)
    assert str(e.value) == 'Only place_id or lat+lon can be specified!'
    with pytest.raises(InvalidArgumentError) as e:
        m.get_point_forecast(place_id='london', lon=14)
    assert str(e.value) == 'Only place_id or lat+lon can be specified!'
    with pytest.raises(InvalidArgumentError) as e:
        m.get_point_forecast(place_id='london', lat=50, lon=14)
    assert str(e.value) == 'Only place_id or lat+lon can be specified!'
    with pytest.raises(InvalidArgumentError) as e:
        m.get_point_forecast(lat=50)
    assert str(e.value) == 'Only place_id or lat+lon can be specified!'
    with pytest.raises(InvalidArgumentError) as e:
        m.get_point_forecast(lon=14)
    assert str(e.value) == 'Only place_id or lat+lon can be specified!'
    with pytest.raises(InvalidArgumentError) as e:
        m.get_point_forecast()
    assert str(e.value) == 'Only place_id or lat+lon can be specified!'

    # Test valid place definitions
    m.get_point_forecast(place_id='london')
    m.get_point_forecast(lat=50, lon=14)


def test_forecast_indexing():
    """Test indexing MultipleTimesData with int, string and datetimes"""
    m = MeteoSource(API_KEY, tiers.PREMIUM)
    # We mock the API requests with sample data
    m.req_handler.execute_request = MagicMock(return_value=SAMPLE_DATA)
    # Get the mocked forecast
    f = m.get_point_forecast(place_id='london')

    # Index by int
    assert f.hourly[1].wind.angle == 106

    # Index by too large int
    with pytest.raises(IndexError):
        assert f.hourly[1000]

    # Index by string
    assert f.hourly['2021-09-08T11:00:00'].feels_like == 23.2

    # Index by string with wrong format
    with pytest.raises(InvalidStrIndex):
        f.hourly['2021-09-08 11:00:00']  # pylint: disable=W0104

    # Index by unsupported type
    with pytest.raises(InvalidIndexType):
        f.hourly[1.1]  # pylint: disable=W0104

    # Index by tz-naive datetime
    dt = datetime.strptime('2021-09-09T00:00:00', F1)
    assert f.hourly[dt].probability.precipitation == 61

    # Index by tz-aware datetime
    dt1 = pytz.timezone('Europe/London').localize(dt)
    assert f.hourly[dt1].probability.precipitation == 61

    # Index by tz-aware datetime but with wrong timezone
    dt2 = pytz.timezone('Asia/Kabul').localize(dt)
    with pytest.raises(InvalidDatetimeIndex) as e:
        f.hourly[dt2]  # pylint: disable=W0104
    err = 'Invalid datetime index "%s" to MultipleTimesData!' % dt2
    assert str(e.value) == err


def test_to_pandas():
    """Test exporting to pandas"""
    m = MeteoSource(API_KEY, tiers.PREMIUM)
    # We mock the API requests with sample data
    m.req_handler.execute_request = MagicMock(return_value=SAMPLE_DATA)
    # Get the mocked forecast
    f = m.get_point_forecast(place_id='london')

    df = f.current.to_pandas()
    assert len(df) == 1

    df = f.minutely.to_pandas()
    assert len(df) == 116
    assert isinstance(df.index, pandas.core.indexes.datetimes.DatetimeIndex)

    df = f.hourly.to_pandas()
    assert len(df) == 155
    assert isinstance(df.index, pandas.core.indexes.datetimes.DatetimeIndex)

    df = f.daily.to_pandas()
    assert len(df) == 30
    assert isinstance(df.index, pandas.core.indexes.datetimes.DatetimeIndex)


def test_to_dict():
    """Test exporting to pandas"""
    m = MeteoSource(API_KEY, tiers.PREMIUM)
    # We mock the API requests with sample data
    m.req_handler.execute_request = MagicMock(return_value=SAMPLE_DATA)
    # Get the mocked forecast
    f = m.get_point_forecast(place_id='london')

    # Test multilevel dict flattening
    assert 'afternoon_wind_angle' in f.daily[0].to_dict()


def test_forecast_structure():
    """Test structure of the Forecast object on real data"""
    # Initialize the MeteoSource object
    m = MeteoSource(API_KEY, tiers.PREMIUM)
    # Get real forecast data (not mocked)
    f = m.get_point_forecast(place_id='london', tz='Asia/Kabul',
                             units=units.METRIC, sections=sections.ALL)

    # Check if the header is correct
    assert isinstance(f, Forecast)
    assert f.lat == 51.50853
    assert f.lon == -0.12574
    assert f.elevation == 25
    assert f.timezone == 'Asia/Kabul'
    assert f.units == 'metric'

    # Check types of the sections
    assert isinstance(f.current, SingleTimeData)
    assert isinstance(f.minutely, MultipleTimesData)
    assert isinstance(f.hourly, MultipleTimesData)
    assert isinstance(f.daily, MultipleTimesData)

    # Check current section
    assert set(f.current.get_members()) == CURRENT
    assert set(f.current.wind.get_members()) == WIND  # pylint: disable=E1101
    # pylint: disable=E1101
    assert set(f.current.precipitation.get_members()) == PRECIPITATION_CURRENT

    # Check minutely section
    assert isinstance(f.minutely.summary, str)
    assert isinstance(f.minutely, MultipleTimesData)
    assert len(f.minutely) > 0
    assert set(f.minutely[0].get_members()) == MINUTELY
    assert isinstance(f.minutely[0].date, datetime)

    # Check hourly section
    assert isinstance(f.hourly, MultipleTimesData)
    assert len(f.hourly) > 0
    assert set(f.hourly[0].get_members()) == HOURLY
    assert set(f.hourly[0].wind.get_members()) == WIND
    assert set(f.hourly[0].cloud_cover.get_members()) == CLOUD
    assert set(f.hourly[0].precipitation.get_members()) == PRECIPITATION
    assert set(f.hourly[0].probability.get_members()) == PROBABILITY

    # Check daily section
    assert isinstance(f.daily, MultipleTimesData)
    assert set(f.daily[0].get_members()) == DAILY
    assert isinstance(f.daily[0].day, datetime)
    assert set(f.daily[0].all_day.get_members()) == ALL_DAY
    assert set(f.daily[0].all_day.wind.get_members()) == WIND
    assert set(f.daily[0].morning.get_members()) == PART_DAY
    assert set(f.daily[0].morning.wind.get_members()) == WIND
    assert set(f.daily[0].afternoon.get_members()) == PART_DAY
    assert set(f.daily[0].afternoon.wind.get_members()) == WIND
    assert set(f.daily[0].evening.get_members()) == PART_DAY
    assert set(f.daily[0].evening.wind.get_members()) == WIND
    assert set(f.daily[0].astro.get_members()) == ASTRO
    assert set(f.daily[0].astro.sun.get_members()) == SUN
    assert set(f.daily[0].astro.moon.get_members()) == MOON
    assert set(f.daily[0].statistics.get_members()) == STATS
    assert set(f.daily[0].statistics.temperature.get_members()) == STATS_TEMP
    assert set(f.daily[0].statistics.wind.get_members()) == STATS_WIND
    assert set(f.daily[0].statistics.precipitation.get_members()) == STATS_PREC