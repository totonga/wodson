#!/bin/bash

#init
function pause(){
    read -p "$*"
}

# Run examples

pause 'Send con parameters [Press key to continue]'
curl -X POST --header 'Content-Type: application/json' --header 'Accept: text/html' -d '[
  {
    "name": "$URL",
    "value": "corbaname::10.89.2.24:900#MeDaMak1.ASAM-ODS"
  },
  {
    "name": "USER",
    "value": "test"
  },
  {
    "name": "PASSWORD",
    "value": "test"
  }
]' 'http://localhost:8081/con/myCon'

pause 'Get Server Model [Press key to continue]'
curl -X GET --header 'Accept: application/json' 'http://localhost:8081/con/myCon/model/access'

pause 'Retrieve name and id from AoTests [Press key to continue]'
curl -X GET --header 'Content-Type: application/json' --header 'Accept: application/json' -d '{
    "AoTest":{},
    "$attributes": {"name":1,"id":1}
}' 'http://localhost:8081/con/myCon/data'

pause 'Retrieve maximal 10 measurements with all query able attribute [Press key to continue]'
curl -X GET --header 'Content-Type: application/json' --header 'Accept: application/json' -d '{
    "AoMeasurement":{},
    "$options":{"$rowlimit":50}
}' 'http://localhost:8081/con/myCon/data'

pause 'Create asam path for instance [Press key to continue]'
curl -X GET --header 'Content-Type: application/json' --header 'Accept: application/problem+json' -d '{
  "entity": "AoTest",
  "id": 1
}' 'http://localhost:8081/con/myCon/utils/asampath/create'

pause 'Retrieve name and id from AoTests using html [Press key to continue]'
curl -X GET --header 'Content-Type: application/json' --header 'Accept: text/html' -d '{
    "AoTest":{},
    "$attributes": {"name":1,"id":1}
}' 'http://localhost:8081/con/myCon/data'
