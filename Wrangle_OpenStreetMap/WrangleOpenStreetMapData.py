
# coding: utf-8

# ## OpenStreetMap Project
# ## Data Wrangling with MongoDB

# Map Area: San Jose, CA, United States
# https://www.openstreetmap.org/relation/112143
# 
# Data file is downloaded from Mapzen, and it is in OSM XML format.
# https://mapzen.com/data/metro-extracts/#san-jose-california
# 
# San Jose is also called "Sillicon Valley", which is home to many high tech companies. I choose this area because I currently live and work in this area. 

# ## Auditing the Data

# In[2]:

# First to use iterative parsing to process the map file and find out what the tags are.
import xml.etree.ElementTree as ET
import pprint

filename = 'san-jose_california.osm'

tags = {}
for event, elem in ET.iterparse(filename):
    if elem.tag in tags:
        tags[elem.tag] += 1
    else:
        tags[elem.tag] = 1
        
pprint.pprint(tags)


# In[3]:

# Second to use regular expression to find different 'key_type'
# "lower", for tags that contain only lowercase letters and are valid,
# "lower_colon", for otherwise valid tags with a colon in their names,
# "problemchars", for tags with problematic characters, and
# "other", for other tags that do not fall into the other three categories.

import re

lower = re.compile(r'^([a-z]|_)*$')
lower_colon = re.compile(r'^([a-z]|_)*:([a-z]|_)*$')
problemchars = re.compile(r'[=\+/&<>;\'"\?%#$@\,\. \t\r\n]')

def key_type(element, keys):
    if element.tag == "tag":
        
        if lower.search(element.attrib['k']):
            keys['lower'] += 1
        elif lower_colon.search(element.attrib['k']):
            keys['lower_colon'] += 1 
        elif problemchars.search(element.attrib['k']):
            keys['problemchars'] += 1
        else:
            keys['other'] += 1 
        
    return keys

def process_map(filename):
    keys = {"lower": 0, "lower_colon": 0, "problemchars": 0, "other": 0}
    for _, element in ET.iterparse(filename):
        keys = key_type(element, keys)

    return keys

process_map(filename)


# In[4]:

# Third, I want to see how many unique users have contributed to this map data.
def process_map(filename):
    users = set()
    for _, element in ET.iterparse(filename):
        if "uid" in element.attrib:
            users.add(element.attrib["uid"])

    return users

users = process_map(filename)
len(users)


# ## Problems with the data

# In[5]:

# First, let's see if there are any unexpected street types comparing to the appropriate ones

from collections import defaultdict

expected_names = ["Street", "Avenue", "Boulevard", "Drive", "Court", "Place", "Square", "Lane", "Road", 
            "Trail", "Parkway", "Commons"]

street_type_re = re.compile(r'\b\S+\.?$', re.IGNORECASE)

def audit_street_type(return_list, search_name, reg_string, expected_list):
    m = reg_string.search(search_name)
    if m:
        street_type = m.group()
        if street_type not in expected_list:
            return_list[street_type].add(search_name)

def is_street_name(elem):
    return (elem.attrib['k'] == "addr:street")

# audit the street type, and return the unexpected ones
def audit(filename, reg_string, expected_list):
    osm_file = open(filename, "r")
    return_list = defaultdict(set)
    for event, elem in ET.iterparse(osm_file, events=("start",)):

        if elem.tag == "node" or elem.tag == "way":
            for tag in elem.iter("tag"):
                if is_street_name(tag):
                    audit_street_type(return_list, tag.attrib['v'], reg_string, expected_list)
    osm_file.close()
    return return_list 

#run the audit for street types
street_types = audit(filename,street_type_re,expected_names)
#print out the unexpected street types
pprint.pprint(dict(street_types))


# The results are quite interesting.
# 
# 1. It seems that I missed some valid street types, such as: Loop, Real, Row. So, I will add them to the expected street types.
# 
# 2. It seems that San Jose area has many unique street names. Such as: Calle de Barcelona, Via San Marino, etc. Maybe because of the Spanish language influence. I will add them to the expected street types as well.
# 
# 3. There are some street types or names I am not sure about. Such as: Ala 680 PM 0.1. Based on my research, it is State of California Department of Transportation maitenance facility location. I really do not know how to handle these data. So, I will keep them as they are too.
# 
# 4. There are a few street types I believe that are wrong and should not be in the dataset. I want to put them in a not_to_import_to_database_list.
# 
# 5. For 'CA': set(['Zanker Rd., San Jose, CA', 'Zanker Road, San Jose, CA']), it looks like someone has entered city and state into street names. I want to fix that.
# 
# 6. For '1': set(['Stewart Drive Suite #1']),
#  '114': set(['West Evelyn Avenue Suite #114']),
#  
#  I will separate the suite number and add to the "unit" attribute.
#  
# 7. For '1425 E Dunne Ave', I will separate the the number '1425' and add to the 'housenumber' attribute.
# 
# 
# 
# 

# In[6]:

# Add street types from the the above 1-3 to expected_names

expected_names = ["Street", "Avenue", "Boulevard", "Drive", "Court", "Place", "Square", "Lane", "Road", 
            "Trail", "Parkway", "Commons", "Circle", "Expressway", "Highway", "Loop", "Real", "Row",
           "Terrace", "Walk", "Way", "Plaza", "0.1", "7.1", "Hamilton", "Alameda", "Auzoa", "Barcelona", "East", 
            "Franklin","Franklin", "Hill","Luna", "Madrid","Marino","Napoli","Ogrodowa","Oro","Palamos", 
            "Paviso","Portofino", "Presada","Seville","Sorrento", "Volante", "West", "Winchester", "robles"
            ] 
                 

# also create a not_import_list for later
not_to_import_list = ["Brunnenweg",u"B\xe4derstra\xdfe", "Cergowska", u"Jana Paw\u0142a II", u"Klosterstra\xdfe", 
                      "Marii Konopnickiej", u"S\u0142owacka"]

# now, rerun the audit
street_types = audit(filename,street_type_re,expected_names)
pprint.pprint(dict(street_types))


# Now, let's do some clean up on the street type.
# 
# 1. Change street type abbreviations to fully spelled street types. Such as "Ave" to "Avenue"
# 2. Fix the street names I believe that are incomplete. For example, "Bascom" should be "Bascom Avenue".

# In[7]:

# create mapping for the street types
mapping_street_type = {
    "Ave": "Avenue",
    "ave": "Avenue",
    "Bascom": "Bascom Avenue",
    "Bellomy": "Bellomy Street",
    "BLVD": "Boulevard",
    "Blvd": "Boulevard",
    "Blvd.": "Boulevard",
    "Cir" : "Circle",
    "Ct": "Court",
    "Dr": "Drive",
    "Hill": "Hill Road",
    "Hwy": "Highway",
    "Julian": "Julian Street",
    "Ln": "Lane",
    "Pkwy": "Parkway",
    "robles": "Robles",
    "Rd": "Road",
    "Rd.": "Road",
    "Sq": "Square",
    "St": "Street",
    "St.": "Street",
    "street": "Street"}


# create an update function
def update_name(name_to_update, mapping, re_string, expected_strings):
    m = re_string.search(name_to_update)
    if m:
        street_return = m.group()
        if street_return not in expected_strings:
            name_to_update = re.sub(re_string, mapping[street_return], name_to_update)

    return name_to_update

#test out to see if the update street name works
for st_type, ways in street_types.iteritems():
    if st_type in mapping_street_type:
        for name in ways:
            #update the street name abbreviations
            new_name = update_name(name, mapping_street_type, street_type_re, expected_names)
            print name, "=>", new_name
                     


# The results look good. Now, I notice some street directions are abbreviated. I want to spell them out.

# In[8]:

# First, let's audit the street directions

# create a regex matching the abbreviations of street directions like "N", "E", "S", "W"
street_direction_re = re.compile(r'^[NSEW]\b\.?', re.IGNORECASE)

# create an expected street directions
expected_directions = ["North", "South", "West", "East"]

# now, run the audit for street direction and print out the results
street_directions = audit(filename, street_direction_re, expected_directions)
pprint.pprint(dict(street_directions))


# In[9]:

# Now let's spell out the street directions

# create mapping for street directions
mapping_street_direction ={
    "E": "East",
    "E.": "East",
    "N": "North",
    "N.": "North",
    "S": "South",
    "S.": "South",
    "W": "West",
    "W.": "West"
}

# Now, let's run the update function and update the street direction abbreviations.

for st_type, ways in street_directions.iteritems():
    if st_type in mapping_street_direction:
        for name in ways:
            #update the street direction abbreviations
            new_name = update_name(name, mapping_street_direction, street_direction_re, expected_directions)
            print name, "=>", new_name


# Now, I also want to look at the postal code.

# In[12]:

def is_postal_code(elem):
    return (elem.attrib['k'] == "addr:postcode")

        
osm_file = open(filename, "r")
return_zip_list = set()
for event, elem in ET.iterparse(osm_file, events=("start",)):

        if elem.tag == "node" or elem.tag == "way":
            for tag in elem.iter("tag"):
                if is_postal_code(tag):
                    return_zip_list.add(tag.attrib['v'])
               
osm_file.close()

pprint.pprint(return_list)


# Now, let's write a function to update the zip code.

# In[16]:

def update_zip_code(zip_in):
    zip_out = ""
    if re.search('[0-9]{5}', zip_in):
        zip_out = re.findall('[0-9]{5}', zip_in)
    return zip_out  

for zip_code in return_zip_list:
    updated_zip = update_zip_code(zip_code)
    print updated_zip


# ## Prepare for MongoDB

# In[17]:

"""
I want to transform the shape of the data into the following shape, write to a json file, then import into MongoDB database.
The output should be a list of dictionaries that look like this:

{
"id": "2406124091",
"type: "node",
"visible":"true",
"created": {
          "version":"2",
          "changeset":"17206049",
          "timestamp":"2013-08-03T16:43:42Z",
          "user":"linuxUser16",
          "uid":"1219059"
        },
"pos": [41.9757030, -87.6921867],
"address": {
          "housenumber": "5157",
          "postcode": "60625",
          "street": "North Lincoln Ave"
        },
"amenity": "restaurant",
"cuisine": "mexican",
"name": "La Cabana De Don Luis",
"phone": "1 (773)-271-5176"
}

"""

# -*- coding: utf-8 -*-
import xml.etree.cElementTree as ET
import pprint
import re
import codecs
import json

lower = re.compile(r'^([a-z]|_)*$')
lower_colon = re.compile(r'^([a-z]|_)*:([a-z]|_)*$')
problemchars = re.compile(r'[=\+/&<>;\'"\?%#$@\,\. \t\r\n]')

CREATED = [ "version", "changeset", "timestamp", "user", "uid"]

def shape_element(element):
    node = {}
    # create an address dictionary
    address = {}
    if element.tag == "node" or element.tag == "way" :
        
        node['type'] = element.tag
        # parse attributes
        for a in element.attrib:
            if a in CREATED:
                if 'created' not in node:
                    node['created'] = {}
                node['created'][a] = element.attrib[a]
            elif a in ['lat', 'lon']:
                if 'pos' not in node:
                    node['pos'] = [None, None]
                if a == 'lat':
                    node['pos'][0] = float(element.attrib[a])
                else:
                    node['pos'][1] = float(element.attrib[a])
            else:
                node[a] = element.attrib[a]
        # iterate tag children
        for tag in element.iter('tag'):
            if not problemchars.search(tag.attrib['k']):
                #tags with single colon
                if lower_colon.search(tag.attrib['k']):
                    #single colon beginning with addr
                    if tag.attrib['k'].find('addr') == 0:
                        if 'address' not in node:
                            node['address'] = {}
                        sub_attr = tag.attrib['k'].split(':', 1)
                        #if it is a street name tag
                        if is_street_name(tag):
                            # not to import the street names I believe that are mistakenly entered for the area
                            if tag.attrib['v'] not in not_to_import_list:
                                # there are a few cases I want to handle manually before importing to MongoDB
                                if tag.attrib['v'] == 'Stewart Drive Suite #1':
                                     address['street'] = 'Stewart Drive'
                                     address['unit'] = 'Suite #1'
                                elif tag.attrib['v'] == 'West Evelyn Avenue Suite #114':
                                     address['street'] = 'West Evelyn Avenue'
                                     address['unit'] = 'Suite #114'
                                elif tag.attrib['v'] == 'Zanker Rd., San Jose, CA' or tag.attrib['v'] == 'Zanker Road, San Jose, CA':
                                     address['street'] = 'Zanker Road'
                                     address['city'] = 'San Jose'
                                     address['state'] = 'CA'
                                elif tag.attrib['v'] == '1425 E Dunne Ave':
                                     address['street'] = 'East Dunne Avenue'
                                     address['housenumber'] = '1425'
                                else:    
                                    #update the street name abbreviations
                                    new_name_1 = update_name(tag.attrib['v'], mapping_street_type, street_type_re, expected_names)
                                    #update the street direction abbreviations
                                    new_name_2 = update_name(new_name_1, mapping_street_direction, street_direction_re, expected_directions)
                                    address[sub_attr[1]] = new_name_2
                        # if it is a postal code tag            
                        elif is_postal_code(tag):
                            #update the postal code
                            new_zip = update_zip_code(tag.attrib['v'])
                            address[sub_attr[1]] = new_zip
                        
                        # not a street name tag, or a postcode tag
                        else:
                             address[sub_attr[1]] = tag.attrib['v']
                    #all other single colons processed normally
                    else:
                        node[tag.attrib['k']] = tag.attrib['v']
                #tags with no colon
                elif tag.attrib['k'].find(':') == -1:
                    node[tag.attrib['k']] = tag.attrib['v']
                    
                #assign the address dictionary to the node    
                if address:
                    node['address'] = address
        # iterate nd children
        for nd in element.iter('nd'):
            if 'node_refs' not in node:
                node['node_refs'] = []
            node['node_refs'].append(nd.attrib['ref'])
            
                   
        
        return node
    else:
        return None

def process_map(file_in, pretty = False):
    # You do not need to change this file
    file_out = "{0}.json".format(file_in)
    data = []
    with codecs.open(file_out, "w") as fo:
        for _, element in ET.iterparse(file_in):
            el = shape_element(element)
            if el:
                data.append(el)
                if pretty:
                    fo.write(json.dumps(el, indent=2)+"\n")
                else:
                    fo.write(json.dumps(el) + "\n")
    return data



# ## Overview of the data

# #### File size

# Original osm file(san-jose_california.osm): 259 MB

# In[19]:

import os
file_size = os.path.getsize("san-jose_california.osm.json")
print file_size


# Converted json file: 297 MB.

# Then, I ran mongoimport in command prompt, and imported the json file. 
# Now that is done, I can run queries to obtain some statistics.

#  #### Number of Documents

# In[21]:

from pymongo import MongoClient
import pprint

db_name = "osm"
client = MongoClient('localhost:27017')
db = client[db_name]
san_jose = db['sanjose']
san_jose.find().count()



# #### Number of Unique Users

# In[22]:

len(san_jose.distinct('created.user'))


# This number is less than the users for the original osm file, which is 1443. This makes sense. When I converted the osm file into a json file, I dropped some streets for which I believed to be wrongfully entered into the map data.

# #### Top Contributing User 

# In[23]:

pipeline = [{"$group" : {"_id" : "$created.user", "count" : {"$sum" : 1}}}, 
            {"$sort" : {"count" : -1}}, 
            {"$limit" : 1}]

def aggregate(db, pipeline):
    return [doc for doc in db.sanjose.aggregate(pipeline)]

if __name__ == '__main__':
    result = aggregate(db, pipeline)
    pprint.pprint(result)


# #### Number of Nodes and Ways

# In[24]:

pipeline = [{"$group" : {"_id" : "$type", "count" : {"$sum" : 1}}}]

if __name__ == '__main__':
    result = aggregate(db, pipeline)
    pprint.pprint(result)


# #### Top 10 Amenities

# In[7]:

pipeline = [{"$match" : {"amenity" : {"$exists" : 1}}}, 
            {"$group" : {"_id" : "$amenity", "count" : {"$sum" : 1}}}, 
            {"$sort" : {"count" : -1}}, 
            {"$limit" : 10}]
 
if __name__ == '__main__':
    result = aggregate(db, pipeline)
    pprint.pprint(result)


# This result was quite surprising to me at first. Why would the top amenity be "parking"? Then it all makes sense. Parking in San jose, a big metropolitan area, is a big problem. It is unique to the area.  

# #### Top 10 Leisures

# In[8]:

pipeline = [{"$match" : {"leisure" : {"$exists" : 1}}}, 
            {"$group" : {"_id" : "$leisure", "count" : {"$sum" : 1}}}, 
            {"$sort" : {"count" : -1}}, 
            {"$limit" : 10}]
if __name__ == '__main__':
    result = aggregate(db, pipeline)
    pprint.pprint(result)


# Again, the result is quite interesting. The top leisure place is "pitch". Then it can be explained by the demographic of the population living in the area. San Jose, the heart of the Sillicon Valley, has a large Indian immigrant population. Baseball and cricket are big sports for the Indian and other immigrant communities. This is very unique comparing to some other parts of America.

# ### Other ideas about the dataset

# #### Zip code for the area

# In[25]:

pipeline = [{"$match": {"address.postcode": {"$exists": 1}}},
            {"$group": {"_id": "$address.postcode", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}]

if __name__ == '__main__':
    result = aggregate(db, pipeline)
    pprint.pprint(result)


# 
# #### Cities in the area

# In[26]:

pipeline = [{"$match" : {"address.city" : {"$exists" : 1}}}, 
            {"$group" : {"_id" : "$address.city", "count" : {"$sum" : 1}}}, 
            {"$sort" : {"count" : -1}}]
            

if __name__ == '__main__':
    result = aggregate(db, pipeline)
    pprint.pprint(result)


# Based on the results for zip codes and cities, I noticed a few things:
# 
# 1. Cities have quite a few problems. 
# Some are in lower case, some are in upper case, and some are not a city in San Jose, some are not even a city.
# For example, "Kayseri" is in Turkey, not San Jose.
# 2. There is some discrepency between the zip codes and cities.
# For example, the most common zip code in the result is "95014", which is at the center of City of Cupertino. It has a count > 9917. However, the count for City of Cupertino is only 52+2=54. This suggests that many entries for City of Cupertino didn't have the postcode entered, or the postcode was entered wrong. Or, many entries with Cupertino zip codes do not have the city name entered.
# 
# Also, it interests me that this is a map for "San Jose" area, but the most common zip code is 95014 (City of Cupertino), and the most common city is Sunnyvale. Neither is San Jose. I would assume that City of San Jose and its zip codes are the most common. But my assumption was wrong.
# 
# Some ideas about improving the dataset for this map area:
# 1. Fix the format issues with city names. Will be a similar process like fixing the street names.
# 2. Put some effort into reducing human errors for entries of cities and zip codes. Developers/users for OpenStreetMap could predefine the cities in the San Jose area and the corresponding zip codes for each city, and leave them in a dropdown list for users to select from. Or, at least a description of the cities and its boundries can be helpful before allowing users to make entries. San Jose area has a high concentration of immigrants. Many immigrants, including users who want to contribute to the map could use some help with familiarizing the area. 
# 3. It seems that parking is of big concern for many users, could we add links to nearby parking for amenity entries? 
# 
# One of the challenges I think, is how to define the "San Jose Area". When I decided to look at this map dataset, I made an assumption that this would be a map of "City of San Jose" and some surrounding areas. However, the dataset's most common zip code or city is NOT even San Jose. So, that brings up a question: what should be included in the "San Jose Area"? Whose standard should we follow? Google Map? State or City government official documents? Are there such documents? I consider this to be important as the answer would help with improvement 1 and 2. 
# 
# For improvement 3, the challenges would be how to propose the new feature to the OpenStreetMap community, what changes need to be done to the API, how are we going to test the new feature, and how are we going to let the new feature to be known by the San Jose user community.

# ### Conclusion

# The dataset for the San Jose area is quite large. The user community who have contributed to the dataset is quite large too. This can be explained by the concentration of high tech companies and workforce in the area.
# 
# However, the dataset has many errors and many entries are incomplete. It interests me that some entries are of foreign languages or foreign places. Many immigrants, including users who want to contribute to the map could use some help from OpenStreetMap and the user community with familiarizing the area. It may help reduce errors and build a more robust dataset.
