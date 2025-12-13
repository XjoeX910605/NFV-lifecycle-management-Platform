#include <CoordTopocentric.h>
#include <CoordGeodetic.h>
#include <Observer.h>
#include <SGP4.h>
#include "getFileData.h"
#include "satellite.h"
#include "AER.h"
#include "InfoProcessing.h"
#include "groundStation.h"
#include "util.h"
#include "json.hpp"

#include <iostream>
#include <iomanip>
#include <map>
#include<fstream>
#include <utility>
#include <numeric>
#include <algorithm>
#include <bitset>
#include <set>
#include <numeric>
using json = nlohmann::json;

namespace InfoProcessing
{
    //印出設定的parameter
    void printParameter(std::map<std::string, std::string> &parameterTable){
        std::cout<<"**********************************************\nparameters:\n----------------------------------------------\n";
        for(auto p:parameterTable){
            std::cout<<p.first<<": "<<p.second<<"\n";
        }
        std::cout<<"**********************************************\n";
    }

    
    
    //印出根據parameter.txt設置位置的地面站，一天中的每一秒有哪些衛星是可以連線的
    void printStationShortestPath(long unsigned int satCountPerOrbit, long unsigned int totalSatCount,std::map<int, satellite::satellite> &satellites, std::map<std::string, std::string> &parameterTable){
        std::ofstream output("./" + parameterTable.at("outputFileName"));


        groundStation::groundStation station1(std::stod(parameterTable.at("stationLatitude1"))
                                            ,std::stod(parameterTable.at("stationLongitude1"))
                                            ,std::stod(parameterTable.at("stationAltitude1")));
        groundStation::groundStation station2(std::stod(parameterTable.at("stationLatitude2"))
                                            ,std::stod(parameterTable.at("stationLongitude2"))
                                            ,std::stod(parameterTable.at("stationAltitude2")));                                    
        double acceptableAzimuthDif = std::stod(parameterTable.at("acceptableAzimuthDif"));
        double acceptableElevationDif = std::stod(parameterTable.at("acceptableElevationDif"));
        double acceptableRange = std::stod(parameterTable.at("acceptableRange"));
        AER acceptableAER_diff("acceptableAER_diff", acceptableAzimuthDif, acceptableElevationDif, acceptableRange);
        int PAT_time = std::stoi(parameterTable.at("PAT_time"));
        int groundStationAcceptableElevation = std::stoi(parameterTable.at("groundStationAcceptableElevation"));
        int groundStationAcceptableDistance = std::stoi(parameterTable.at("groundStationAcceptableDistance"));
        int time = std::stoi(parameterTable.at("time"));
        bool round = parameterTable.at("round") == "Y";
        std::vector<int> availableSatsList1 = station1.getSecondCoverSatsList(satellites, time, groundStationAcceptableElevation, groundStationAcceptableDistance, round);
        std::vector<int> availableSatsList2 = station2.getSecondCoverSatsList(satellites, time, groundStationAcceptableElevation, groundStationAcceptableDistance, round);
        std::vector<std::vector<int>> medium(totalSatCount, std::vector<int>(totalSatCount, -1));
        std::vector<std::vector<int>> constellationShortestDistance = satellite::getConstellationShortestPathRecordMedium(satCountPerOrbit, totalSatCount, time, PAT_time, acceptableAER_diff, satellites, medium);
        //std::vector<std::vector<int>> distance = satellite::getConstellationShortestPath(satCountPerOrbit,totalSatCount, time, PAT_time,acceptableAER_diff, satellites);
        for(size_t i = 0; i < constellationShortestDistance.size(); ++i){ //印出整個hop count array
            for(size_t j = i; j < constellationShortestDistance.size(); ++j){
                size_t sourceId = (size_t)satellite::indexToSatId(i, satCountPerOrbit);
                size_t destId = (size_t)satellite::indexToSatId(j, satCountPerOrbit);
                
                output<<"sat"<<sourceId<<" to sat"<<destId<<": ";
                output<<std::setw(6)<<constellationShortestDistance[i][j]<<"  ,path: ";
                std::vector<int> path = satellite::getPath(satCountPerOrbit, sourceId, destId, medium, constellationShortestDistance);
                for(auto v: path)
                    output<<v<<" ";
                output<<"\n";
            }
        }
        
        /*
        std::cout<<"\n\n\n---------------------------------------------\n";
        //在terminal中印出observerId衛星到otherId衛星所經過的衛星
        std::cout<<""<<distance;
        for(auto v: distance)
            std::cout<<v<<" ";
        std::cout<<"\n---------------------------------------------\n";
        output.close();    
        */   
    }

    
    void printStationHopcountPath(long unsigned int satCountPerOrbit, long unsigned int totalSatCount, std::map<int, satellite::satellite> &satellites, std::map<std::string, std::string> &parameterTable){
        std::ofstream output("./" + parameterTable.at("outputFileName"));

        json json_output;

        groundStation::groundStation station1(std::stod(parameterTable.at("stationLatitude1"))
                                            ,std::stod(parameterTable.at("stationLongitude1"))
                                            ,std::stod(parameterTable.at("stationAltitude1")));
        groundStation::groundStation station2(std::stod(parameterTable.at("stationLatitude2"))
                                            ,std::stod(parameterTable.at("stationLongitude2"))
                                            ,std::stod(parameterTable.at("stationAltitude2")));  

        double acceptableAzimuthDif = std::stod(parameterTable.at("acceptableAzimuthDif"));
        double acceptableElevationDif = std::stod(parameterTable.at("acceptableElevationDif"));
        double acceptableRange = std::stod(parameterTable.at("acceptableRange"));
        AER acceptableAER_diff("acceptableAER_diff", acceptableAzimuthDif, acceptableElevationDif, acceptableRange);
        int time = std::stoi(parameterTable.at("time"));
        int PAT_time = std::stoi(parameterTable.at("PAT_time"));
        int groundStationAcceptableElevation = std::stoi(parameterTable.at("groundStationAcceptableElevation"));
        int groundStationAcceptableDistance = std::stoi(parameterTable.at("groundStationAcceptableDistance"));
        bool round = parameterTable.at("round") == "Y";
        std::vector<int> availableSatsList1 = station1.getSecondCoverSatsList(satellites, time, groundStationAcceptableElevation, groundStationAcceptableDistance, round);
        std::vector<int> availableSatsList2 = station2.getSecondCoverSatsList(satellites, time, groundStationAcceptableElevation, groundStationAcceptableDistance, round);
        
        std::vector<std::vector<int>> medium(totalSatCount, std::vector<int>(totalSatCount, -1));
        std::vector<std::vector<int>> constellationHopCount = satellite::getConstellationHopCountRecordMedium(satCountPerOrbit, totalSatCount, time, PAT_time, acceptableAER_diff, satellites, medium);
        size_t sourceId = (size_t)std::stoi(parameterTable.at("observerId"));
        size_t destId = (size_t)std::stoi(parameterTable.at("otherId"));
        
        std::cout<<"\n\nstation1 :\n";
        for(auto v: availableSatsList1)
            std::cout<<v<<" ";
        std::cout<<"\n\nstation2 :\n";
        for(auto v: availableSatsList2)
            std::cout<<v<<" ";

        json_output["availableSatsList1"] = availableSatsList1;
        json_output["availableSatsList2"] = availableSatsList2;

        std::vector<std::vector<int>> pathlist;
        std::cout<<"\n\n\n---------------------------------------------";
        std::vector<int> LeastHopPath = satellite::getPath(satCountPerOrbit, std::stoi(std::to_string(availableSatsList1.at(0))), std::stoi(std::to_string(availableSatsList2.at(0))), medium, constellationHopCount);
        //在terminal中印出observerId衛星到otherId衛星所經過的衛星
        for(auto i:availableSatsList1){
            for(auto j:availableSatsList2){
                std::vector<int> path = satellite::getPath(satCountPerOrbit, std::stoi(std::to_string(i)), std::stoi(std::to_string(j)), medium, constellationHopCount);
                if(path.size()<=LeastHopPath.size())
                    LeastHopPath = satellite::getPath(satCountPerOrbit, std::stoi(std::to_string(i)), std::stoi(std::to_string(j)), medium, constellationHopCount);
                std::cout<<"\n\npath from sat"<<i<<" to "<<"sat"<<j<<":\n";
                for(auto v: path)
                    std::cout<<v<<" ";
                pathlist.push_back(path);
            }
        }

        json_output["pathlist"] = pathlist;
        output << json_output.dump(4);
        
        std::cout<<"\n\n---------------------------------------------\n\n";
        std::cout<<"Least Hop Count path:\n";
        for(auto v: LeastHopPath)
            std::cout<<v<<" ";
        std::cout<<"\n\n---------------------------------------------\n\n";

        output.close(); 

    }

    void printStationCoverSats(std::map<int, satellite::satellite> &satellites, std::map<std::string, std::string> &parameterTable){
        std::ofstream output("./" + parameterTable.at("outputFileName"));

        groundStation::groundStation station(std::stod(parameterTable.at("stationLatitude"))
                                            ,std::stod(parameterTable.at("stationLongitude"))
                                            ,std::stod(parameterTable.at("stationAltitude")));
        int groundStationAcceptableElevation = std::stoi(parameterTable.at("groundStationAcceptableElevation"));
        int groundStationAcceptableDistance = std::stoi(parameterTable.at("groundStationAcceptableDistance"));
        bool round = parameterTable.at("round") == "Y";
        int time = std::stoi(parameterTable.at("time"));
    
        std::vector<int> availableSatsList = station.getSecondCoverSatsList(satellites, time, groundStationAcceptableElevation, groundStationAcceptableDistance, round);
        output<<"t = "<<time<<":  ";
        if(availableSatsList.empty()){
            output<<"All can not connect!";
        }
        for(auto id: availableSatsList){
            output<<id<<",  ";
        }
        output<<"\n";
        
        // for(size_t t = time; t < 86400; ++t){
        //     std::vector<int> availableSatsList = station.getSecondCoverSatsList(satellites, t, groundStationAcceptableElevation, groundStationAcceptableDistance, round);
        //     output<<"t = "<<t<<":  ";
        //     if(availableSatsList.empty()){
        //         output<<"All can not connect!";
        //     }
        //     for(auto id: availableSatsList){
        //         output<<id<<",  ";
        //     }
        //     output<<"\n";
        // }

        output.close();       
    }
    
}


