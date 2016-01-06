#Wodson - Feasability Study


## Prepare

Download omniORBpy package
http://sourceforge.net/projects/omniorb/files/omniORBpy/

Copy omniorb runtime or add it to path

```
cp omniORBpy-4.2.1-win64-python27\lib\x86_win32\*.* env\Scripts\.
cp omniORBpy-4.2.1-win64-python27\bin\x86_win32\*.* env\Scripts\.
```

Create python stub

```
\env\Scripts\omniidl.exe -bpython ODS53.IDL
```

Include omiorb and stub into pythonpath

```
set PYTHONPATH=%PYTHONPATH%;???\omniORBpy-4.2.1-win64-python27\lib\python;???
```

## curl commands

```
curl -X PUT "http://localhost:8080/context" -d "[{\"name\":\"URL\",\"value\":\"corbaname::localhost:2809/NameService#AtfxTest.ASAM-ODS\"},{\"name\":\"USER\",\"value\":\"System\"},{\"name\":\"PASSWORD\",\"value\":\"puma\"}]" --header "Content-Type: application/json" --header "Accept: application/json"
curl -X GET "http://localhost:8080/context" --header "Accept: application/json"
curl -X GET "http://localhost:8080/schema"  --header "Accept: application/json"

curl -X PUT "http://localhost:8080/schema" -d"{\"entities\":[{\"name\":\"MyAny\",\"baseName\":\"AoAny\",\"relations\":[{\"name\":\"myMeasurment\",\"kind\":\"INFO\",\"inverseName\":\"myInfoElement\",\"obligatory\":false,\"type\":\"n-1\",\"relEntityName\":\"Measurement\"}],\"attributes\":[{\"name\":\"Id\",\"baseName\":\"id\"},{\"name\":\"Name\",\"baseName\":\"name\"},{\"name\":\"my_classification\",\"dataType\":\"DT_DOUBLE\",\"obligatory\":true}]}]}" --header "Content-Type:application/json"
curl -X DELETE "http://localhost:8080/schema" -d"{\"entities\":[{\"name\":\"MyAny\"}]}" --header "Content-Type:application/json"

curl -X GET  "http://localhost:8080/querydata" -d "{\"entityName\":\"MeaQuantity\"}" --header "Content-Type: application/json" --header "Accept: application/json"
curl -X POST "http://localhost:8080/querydata" -d "{\"entityName\":\"MeaQuantity\"}" --header "Content-Type: application/json" --header "Accept: application/json"
curl -X GET  "http://localhost:8080/querydata" -d "{\"entityName\":\"MeaQuantity\",\"attributes\":[\"name\",\"id\"]}" --header "Content-Type: application/json" --header "Accept: application/json"
curl -X GET  "http://localhost:8080/querydata" -d "{\"entityName\":\"MeaQuantity\",\"conditions\":[\"id=4\"]}" --header "Content-Type: application/json" --header "Accept: application/json"

curl -X GET "http://localhost:8080/querydata" -d "{\"entityName\":\"MeaQuantity\",\"attributes\":[\"name\",\"id\"],\"conditions\":[\"measurement=2\"]}"    --header "Content-Type: application/json" --header "Accept: application/json" 
curl -X GET "http://localhost:8080/querydata" -d "{\"entityName\":\"MeaQuantity\",\"attributes\":[\"name\",\"id\"],\"conditions\":[\"measurement.id=2\"]}" --header "Content-Type: application/json" --header "Accept: application/json" 
curl -X GET "http://localhost:8080/querydata" -d "{\"entityName\":\"MeaQuantity\",\"attributes\":[\"name\",\"id\"],\"conditions\":[\"id=4\"]}"             --header "Content-Type: application/json" --header "Accept: application/json" 

curl -X GET "http://localhost:8080/querydata" -d "{\"entityName\":\"MeaQuantity\",\"attributes\":[\"DISTINCT(name)\"]}"  --header "Content-Type: application/json" --header "Accept: application/json" 

curl -X GET "http://localhost:8080/querydata" -d "{\"entityName\":\"MeaQuantity\",\"attributes\":[\"name\"],\"orderBy\":[\"name\"]}"              --header "Content-Type: application/json" --header "Accept: application/json" 
curl -X GET "http://localhost:8080/querydata" -d "{\"entityName\":\"MeaQuantity\",\"attributes\":[\"name\"],\"orderBy\":[\"ASCENDING(name)\"]}"   --header "Content-Type: application/json" --header "Accept: application/json" 
curl -X GET "http://localhost:8080/querydata" -d "{\"entityName\":\"MeaQuantity\",\"attributes\":[\"name\"],\"orderBy\":[\"DESCENDING(name)\"]}"  --header "Content-Type: application/json" --header "Accept: application/json" 

curl -X GET "http://localhost:8080/querydata" -d "{\"entityName\":\"LocalColumn\"}"                                                       --header "Content-Type: application/json" --header "Accept: application/json"
curl -X GET "http://localhost:8080/querydata" -d "{\"entityName\":\"LocalColumn\",\"attributes\":[\"id\"],\"conditions\":[\"id=12\"]}"    --header "Content-Type: application/json" --header "Accept: application/json" 

curl -X GET "http://localhost:8080/querydata" -d "{\"entityName\":\"LocalColumn\",\"conditions\":[\"id=12\"],\"attributes\":[\"id\",\"values\"]}"                                                                                 --header "Content-Type: application/json" --header "Accept: application/json" 
curl -X GET "http://localhost:8080/querydata" -d "{\"entityName\":\"LocalColumn\",\"conditions\":[\"id=12\"],\"attributes\":[\"id\",\"values\",\"flags\"]}"                                                                       --header "Content-Type: application/json" --header "Accept: application/json" 
curl -X GET "http://localhost:8080/querydata" -d "{\"entityName\":\"LocalColumn\",\"conditions\":[\"id=12\"],\"attributes\":[\"id\",\"values\",\"flags\",\"generation_parameters\"]}"                                             --header "Content-Type: application/json" --header "Accept: application/json" 
curl -X GET "http://localhost:8080/querydata" -d "{\"entityName\":\"LocalColumn\",\"conditions\":[\"id=12\"],\"attributes\":[\"id\",\"values\",\"flags\",\"generation_parameters\"],\"vectorMaxCount\":10}"                       --header "Content-Type: application/json" --header "Accept: application/json" 
curl -X GET "http://localhost:8080/querydata" -d "{\"entityName\":\"LocalColumn\",\"conditions\":[\"id=12\"],\"attributes\":[\"id\",\"values\",\"flags\",\"generation_parameters\"],\"vectorSkipCount\":5,\"vectorMaxCount\":10}" --header "Content-Type: application/json" --header "Accept: application/json" 
```

##SimpleQueryStructure Explanation

### Meta information

- Get all attributes of the given entity

```json
{
	"entityName": "MeaQuantity"
}
```

- Get maximal 10 rows of all attributes of the given entity

```json
{
	"entityName": "MeaQuantity",
	"maxCount": 50
}
```

- Get id and name attribute of the given entity

```json
{
	"entityName": "MeaQuantity",
	"attributes": ["name","id"]
}
```

- Get id and name attribute of the given entity and the name attribute of the related measurement

```json
{
	"entityName": "MeaQuantity",
	"attributes": ["name","id","measurement.name"]
}
```

- Get all attributes if the given instance

```json
{
	"entityName": "MeaQuantity",
	"conditions": ["id=4"]
}
```

- Get name and id of the MeasurementQuantities of the Measurement with id=2

```json
{
	"entityName": "MeaQuantity",
	"attributes": ["name","id"],
	"conditions": ["measurement=2"]
}
```

- Get information about all MeasurementQuantities of a the SubTest with id=2

```json
{
	"entityName": "MeaQuantity",
	"attributes": ["name","id","measurement.name","measurement.id"],
	"conditions": ["measurement.test=2"]
}
```

- Get DISTINCT of all MeasurementQuantity names

```json
{
	"entityName": "MeaQuantity",
	"attributes": ["DISTINCT(name)"]
}
```

- Get names of given entity in descending order

```json
{
	"entityName": "MeaQuantity",
	"attributes": ["name"],
	"orderBy": ["DESCENDING(name)"]
}
```

### Bulk data

- Get values, flags and generation_parameters of the given localcolumn

```json
{
	"entityName": "LocalColumn",
	"conditions": ["id=12"],
	"attributes": ["id","values","flags","generation_parameters"]
}
```

- Get id, values, flags and generation_parameters of all local columns of the Submatrix with id=8

```json
{
	"entityName": "LocalColumn",
	"conditions": ["submatrix=8"],
	"attributes": ["id","values","flags","generation_parameters"],
	"vectorMaxCount": 1000
}
```

- Get next chunk of values and flags of the given submatrix

```json
{
	"entityName": "LocalColumn",
	"conditions": ["submatrix=8"],
	"attributes": ["id","values","flags"],
	"vectorSkipCount": 1000,
	"vectorMaxCount": 100
}
```
