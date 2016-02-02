# Wodson - Feasability Study

## Content
- [Curl Commands](#curl-commands)
- [QueryStructureV1 Explanation](#simpleQueryStructure-explanation)
- [Modify Schema](#modify-schema)
- [Setup System](#setup-system)

## Curl Commands

```
curl.exe -X PUT "http://localhost:8081/context" -d "[{\"name\":\"URL\",\"value\":\"corbaname::localhost:2809/NameService#AtfxTest.ASAM-ODS\"},{\"name\":\"USER\",\"value\":\"System\"},{\"name\":\"PASSWORD\",\"value\":\"puma\"}]" --header "Content-Type: application/json" --header "Accept: application/json"
curl.exe -X GET "http://localhost:8081/context" --header "Accept: application/json"
curl.exe -X GET "http://localhost:8081/schema"  --header "Accept: application/json"

curl.exe -X PUT "http://localhost:8081/schema" -d"{\"entities\":[{\"name\":\"MyAny\",\"baseName\":\"AoAny\",\"relations\":[{\"name\":\"myMeasurment\",\"kind\":\"INFO\",\"inverseName\":\"myInfoElement\",\"obligatory\":false,\"type\":\"n-1\",\"relEntityName\":\"Measurement\"}],\"attributes\":[{\"name\":\"Id\",\"baseName\":\"id\"},{\"name\":\"Name\",\"baseName\":\"name\"},{\"name\":\"my_classification\",\"dataType\":\"DT_DOUBLE\",\"obligatory\":true}]}]}" --header "Content-Type:application/json"
curl.exe -X DELETE "http://localhost:8081/schema" -d"{\"entities\":[{\"name\":\"MyAny\"}]}" --header "Content-Type:application/json"

curl.exe -X GET  "http://localhost:8081/data" -d "{\"entity\":\"MeaQuantity\"}" --header "Content-Type: application/json" --header "Accept: application/json"
curl.exe -X POST "http://localhost:8081/dataGP" -d "{\"entity\":\"MeaQuantity\"}" --header "Content-Type: application/json" --header "Accept: application/json"
curl.exe -X GET  "http://localhost:8081/data" -d "{\"entity\":\"MeaQuantity\",\"attributes\":[\"name\",\"id\"]}" --header "Content-Type: application/json" --header "Accept: application/json"
curl.exe -X GET  "http://localhost:8081/data" -d "{\"entity\":\"MeaQuantity\",\"conditions\":[\"id=4\"]}" --header "Content-Type: application/json" --header "Accept: application/json"

curl.exe -X GET "http://localhost:8081/data" -d "{\"entity\":\"MeaQuantity\",\"attributes\":[\"name\",\"id\"],\"conditions\":[\"measurement=2\"]}"    --header "Content-Type: application/json" --header "Accept: application/json" 
curl.exe -X GET "http://localhost:8081/data" -d "{\"entity\":\"MeaQuantity\",\"attributes\":[\"name\",\"id\"],\"conditions\":[\"measurement.id=2\"]}" --header "Content-Type: application/json" --header "Accept: application/json" 
curl.exe -X GET "http://localhost:8081/data" -d "{\"entity\":\"MeaQuantity\",\"attributes\":[\"name\",\"id\"],\"conditions\":[\"id=4\"]}"             --header "Content-Type: application/json" --header "Accept: application/json" 

curl.exe -X GET "http://localhost:8081/data" -d "{\"entity\":\"MeaQuantity\",\"attributes\":[\"DISTINCT(name)\"]}"  --header "Content-Type: application/json" --header "Accept: application/json" 

curl.exe -X GET "http://localhost:8081/data" -d "{\"entity\":\"MeaQuantity\",\"attributes\":[\"name\"],\"orderBy\":[\"name\"]}"              --header "Content-Type: application/json" --header "Accept: application/json" 
curl.exe -X GET "http://localhost:8081/data" -d "{\"entity\":\"MeaQuantity\",\"attributes\":[\"name\"],\"orderBy\":[\"ASCENDING(name)\"]}"   --header "Content-Type: application/json" --header "Accept: application/json" 
curl.exe -X GET "http://localhost:8081/data" -d "{\"entity\":\"MeaQuantity\",\"attributes\":[\"name\"],\"orderBy\":[\"DESCENDING(name)\"]}"  --header "Content-Type: application/json" --header "Accept: application/json" 

curl.exe -X GET "http://localhost:8081/data" -d "{\"entity\":\"LocalColumn\"}"                                                       --header "Content-Type: application/json" --header "Accept: application/json"
curl.exe -X GET "http://localhost:8081/data" -d "{\"entity\":\"LocalColumn\",\"attributes\":[\"id\"],\"conditions\":[\"id=12\"]}"    --header "Content-Type: application/json" --header "Accept: application/json" 

curl.exe -X GET "http://localhost:8081/data" -d "{\"entity\":\"LocalColumn\",\"conditions\":[\"id=12\"],\"attributes\":[\"id\",\"values\"]}"                                                                                 --header "Content-Type: application/json" --header "Accept: application/json" 
curl.exe -X GET "http://localhost:8081/data" -d "{\"entity\":\"LocalColumn\",\"conditions\":[\"id=12\"],\"attributes\":[\"id\",\"values\",\"flags\"]}"                                                                       --header "Content-Type: application/json" --header "Accept: application/json" 
curl.exe -X GET "http://localhost:8081/data" -d "{\"entity\":\"LocalColumn\",\"conditions\":[\"id=12\"],\"attributes\":[\"id\",\"values\",\"flags\",\"generation_parameters\"]}"                                             --header "Content-Type: application/json" --header "Accept: application/json" 
curl.exe -X GET "http://localhost:8081/data" -d "{\"entity\":\"LocalColumn\",\"conditions\":[\"id=12\"],\"attributes\":[\"id\",\"values\",\"flags\",\"generation_parameters\"],\"vectorMaxCount\":10}"                       --header "Content-Type: application/json" --header "Accept: application/json" 
curl.exe -X GET "http://localhost:8081/data" -d "{\"entity\":\"LocalColumn\",\"conditions\":[\"id=12\"],\"attributes\":[\"id\",\"values\",\"flags\",\"generation_parameters\"],\"vectorSkipCount\":5,\"vectorMaxCount\":10}" --header "Content-Type: application/json" --header "Accept: application/json" 
```

## QueryStructureV1 Explanation

### Meta information

- Get all attributes of the given entity

```json
{
	"entity": "MeaQuantity"
}
```

- Get all attributes of the first entity derived from this base type

```json
{
	"entity": "AoTest"
}
```

- Get all attributes of the entity with the aid/objecttype

```json
{
	"entity": "1"
}
```

- Get maximal 10 rows of all attributes of the given entity

```json
{
	"entity": "MeaQuantity",
	"maxCount": 50
}
```

- Get id and name attribute of the given entity

```json
{
	"entity": "MeaQuantity",
	"attributes": ["name","id"]
}
```

- Get id and name attribute of the given entity and the name attribute of the related measurement

```json
{
	"entity": "MeaQuantity",
	"attributes": ["name","id","measurement.name"]
}
```

- Get all attributes if the given instance

```json
{
	"entity": "MeaQuantity",
	"conditions": ["id=4"]
}
```

- Get name and id of the MeasurementQuantities of the Measurement with id=2

```json
{
	"entity": "MeaQuantity",
	"attributes": ["name","id"],
	"conditions": ["measurement=2"]
}
```

- Get information about all MeasurementQuantities of a the SubTest with id=2

```json
{
	"entity": "MeaQuantity",
	"attributes": ["name","id","measurement.name","measurement.id"],
	"conditions": ["measurement.test=2"]
}
```

- Get DISTINCT of all MeasurementQuantity names

```json
{
	"entity": "MeaQuantity",
	"attributes": ["DISTINCT(name)"]
}
```

- Get names of given entity in descending order

```json
{
	"entity": "MeaQuantity",
	"attributes": ["name"],
	"orderBy": ["DESCENDING(name)"]
}
```

### Bulk data

- Get values, flags and generation_parameters of the given localcolumn

```json
{
	"entity": "LocalColumn",
	"conditions": ["id=12"],
	"attributes": ["id","values","flags","generation_parameters"]
}
```

- Get id, values, flags and generation_parameters of all local columns of the Submatrix with id=8

```json
{
	"entity": "LocalColumn",
	"conditions": ["submatrix=8"],
	"attributes": ["id","values","flags","generation_parameters"],
	"vectorMaxCount": 1000
}
```

- Get next chunk of values and flags of the given submatrix

```json
{
	"entity": "LocalColumn",
	"conditions": ["submatrix=8"],
	"attributes": ["id","values","flags"],
	"vectorSkipCount": 1000,
	"vectorMaxCount": 100
}
```

## Modify Schema

### Create schema POST

- Create an entity with attributes and relations

```json
{
	"entities": [{
		"name": "MyAny",
		"baseName": "AoAny",
		"relations": [{
			"name": "myMeasurment",
			"kind": "INFO",
			"inverseName": "myInfoElement",
			"obligatory": false,
			"type": "n-1",
			"relEntityName": "Measurement"
		}],
		"attributes": [{
			"name": "Id",
			"baseName": "id"
		},
		{
			"name": "Name",
			"baseName": "name"
		},
		{
			"name": "my_classification",
			"dataType": "DT_DOUBLE",
			"obligatory": true
		}]
	}]
}
```

### Delete stuff using schema DELETE

- delete an entity

```json
{
	"entities": [{
		"name": "MyAny"
	}]
}
```

### Utils

### AsamPath

- Create an asam path

```sh
pause 'Create asam path for instance [Press key to continue]'
curl -X GET --header 'Content-Type: application/json' --header 'Accept: application/problem+json' -d '{
  "entity": "Projekt",
  "id": 1
}' 'http://localhost:8081/utils/asampath/create'
```

- Resolve an asam path

```sh
curl -X POST --header 'Content-Type: application/json' --header 'Accept: application/json' -d '{
  "path": "/[Environment]testenv;1/[Projekt]Project;V1"
}' 'http://localhost:8081/utils/asampath/resolve'
```



## Setup System

### Linux

Run the folloowing commands in a terminal.

```sh
sudo apt-get install python omniidl-python python-pip git
mkdir dev
cd dev
git clone https://github.com/totonga/wodson.git
cd wodson/feasability_study/
omniidl -bpython corbaserver.idl
pip install --user -r requirements.txt
python app.py
```

Visit http://localhost:8081/ui/ to see the swagger help

Get some development tools

```sh
sudo apt-get install eric curl
```

### Windows

Download omniORBpy package
http://sourceforge.net/projects/omniorb/files/omniORBpy/

Copy omniorb runtime or add it to path
Add omniorb python components to PYTHONPATH 
```
set PYTHONPATH=%PYTHONPATH%;???\omniORBpy-4.2.1-win64-python27\lib\python
```

If Visual Studio 2015 si used the omniorb runtime can be copied to an environment
```
cp omniORBpy-4.2.1-win64-python27\lib\x86_win32\*.* env\Scripts\.
cp omniORBpy-4.2.1-win64-python27\bin\x86_win32\*.* env\Scripts\.
```

Create python stub

```
\env\Scripts\omniidl.exe -bpython corbaserver.IDL
```

Include omiorb and stub into pythonpath

```
set PYTHONPATH=%PYTHONPATH%;???\omniORBpy-4.2.1-win64-python27\lib\python;???
```

