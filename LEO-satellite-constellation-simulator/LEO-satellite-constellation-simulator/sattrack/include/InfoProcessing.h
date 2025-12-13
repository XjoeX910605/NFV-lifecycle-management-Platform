#ifndef INFO_PROCESSING_H
#define INFO_PROCESSING_H
#include <CoordTopocentric.h>
#include <CoordGeodetic.h>
#include <Observer.h>
#include <SGP4.h>
#include "getFileData.h"
#include "satellite.h"
#include "AER.h"
#include "json.hpp"

#include <iostream>
#include <iomanip>
#include<map>
#include<fstream>
#include <utility>
#include <numeric>
#include <algorithm>
#include <bitset>
#include <set>

namespace InfoProcessing
{

    
    void printStationShortestPath(long unsigned int satCountPerOrbit, long unsigned int totalSatCount, std::map<int, satellite::satellite> &satellites, std::map<std::string, std::string> &parameterTable);
    
    void printStationHopcountPath(long unsigned int satCountPerOrbit, long unsigned int totalSatCount, std::map<int, satellite::satellite> &satellites, std::map<std::string, std::string> &parameterTable);

    void printStationCoverSats(std::map<int, satellite::satellite> &satellites, std::map<std::string, std::string> &parameterTable);
}

#endif