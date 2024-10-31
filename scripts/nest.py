 #!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NEST download tools

Copyright (C) 2022-2023 Christian T. Steigies <steigies@physik.uni-kiel.de>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

__author__ = "Christian T. Steigies <steigies@physik.uni-kiel.de>"
__license__ = "GPL License"

# --------------------------------------------------------------------------
tables = {"e": "corr_for_efficiency",
          "c": "corr_for_pressure",
          "u": "uncorrected",
          "p": "pressure_mbar"}

# --------------------------------------------------------------------------
def dates(dt):
    Y = dt.year
    M = dt.month
    D = dt.day
    h = dt.hour
    m = dt.minute

    return (Y, M, D, h, m)


# --------------------------------------------------------------------------
def multi(station, table, data, start, end):
    """
    query NEST for multiple stations, single data type

    Parameters
    ----------
    station : [str]
        list of station names
    table : str
        revori, ori, or 1h data
    data : str
        corrected (c, e), uncorrected (u), or pressure (p)
    start, end : datetime
        start and end of timeinterval for data

    Returns
    -------
    NEST string

    """
    
    value = "https://www.nmdb.eu/nest/draw_graph.php?wget=1"

    # use a copy of the list as the list is modified by using pop
    stations = station.copy()
    while len(stations):
        s = stations.pop(0)
        value += "&stations[]=%s" %(s.upper())
    value += "&output=ascii"
    if table in ["revori", "ori", "1h"]:
        value += "&tabchoice=%s" %(table)
    else:
        raise ValueError  # table not defined
    try:
        value += "&odtype[]=%s" % (tables[data])
    except:
        raise ValueError  # data type not defined
    value += "&date_choice=bydate"
    value += "&start_year=%04i&start_month=%02i&start_day=%02i&start_hour=%02i&start_min=%02i" % (dates(start))
    value += "&end_year=%04i&end_month=%02i&end_day=%02i&end_hour=%02i&end_min=%02i"  % (dates(end))
    value += "&yunits=0"

    return(value)


# --------------------------------------------------------------------------
def single(station, table, data, start, end):
    """
    query NEST for single station, multiple data types

    Parameters
    ----------
    station : str
        station name
    table : str
        revori, ori, or 1h data
    data : [str]
        corrected (c, e), uncorrected (u), or pressure (p)
    start, end : datetime
        start and end of timeinterval for data

    Raises
    ------
    ValueError
        for undefined tables or data types

    Returns
    -------
    NEST string
    """

    value = "https://www.nmdb.eu/nest/draw_graph.php?wget=1"
    value += "&stations[]=%s" %(station.upper())
    value += "&output=ascii"
    if table in ["revori", "ori", "1h"]:
        value += "&tabchoice=%s" % (table)
    else:
        raise ValueError  # table not defined

    # use a copy of the list as the list is modified by using pop
    dtype = data.copy()
    d = dtype.pop(0)
    try:
        value += "&dtype=%s" % (tables[d])
    except:
        raise ValueError  # data type not defined
    while len(dtype):
        d = dtype.pop(0)
        try:
            value += "&odtype[]=%s" % (tables[d])
        except:
            raise ValueError  # extra data type not defined
    value += "&date_choice=bydate"
    value += "&start_year=%04i&start_month=%02i&start_day=%02i&start_hour=%02i&start_min=%02i" % (dates(start))
    value += "&end_year=%04i&end_month=%02i&end_day=%02i&end_hour=%02i&end_min=%02i"  % (dates(end))
    value += "&yunits=0"

    return(value)


# --------------------------------------------------------------------------
def header(download):
    """
    return NEST header with meta data

    Parameters
    ----------
    download : NEST string

    Returns
    -------
    header
    """
    import urllib.request

    data = urllib.request.urlopen(download)
    Header = ""
    for line in data:
        if line[0] == 35: # NEST headers start with '#' == ASCII 35
            Header += line[1:].decode() # remove the '#' from the header

    return(Header)


# --------------------------------------------------------------------------
