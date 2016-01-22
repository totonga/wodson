#!/bin/bash

#init
function pause(){
    read -p "$*"
}

# Run examples

pause 'Send context variables [Press key to continue]'
curl -X PUT --header 'Content-Type: application/json' --header 'Accept: text/html' -d '[
  {
    "name": "URL",
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
]' 'http://localhost:8080/context'

pause 'Get Server Schema [Press key to continue]'
curl -X GET --header 'Accept: application/json' 'http://localhost:8080/schema'

pause 'Retrieve name and id from AoTests [Press key to continue]'
curl -X GET --header 'Content-Type: application/json' --header 'Accept: application/json' -d '{
    "entityName": "AoTest",
    "attributes": ["name","id"]
}' 'http://localhost:8080/data'

pause 'Retrieve maximal 10 measurements with all query able attribute [Press key to continue]'
curl -X GET --header 'Content-Type: application/json' --header 'Accept: application/json' -d '{
    "entityName": "AoMeasurement",
    "maxCount": 50
}' 'http://localhost:8080/data'
