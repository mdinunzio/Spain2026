# Goal

I am using this repo as a suite of tools to help organize and plan my upcoming trip in Spain from roughly Sat Aug 29, 2026 to Fri Sep 11, 2026. We will be visiting Mallorca and Costa Brava and are trying to help sort out our activities, restaurants, and logistics.

At your disposal is the mgdio package and corresponding skill. This should allow you to view all files in the Spain Google Drive folder we've set up, as well as edit the Spain 2026 spreadsheet. Additionally you should be able to use the Maps API to geocode locations we are interested in.

## Final Product

Ultimately I like to organize my trips in the following way, and this is the desired end result.

1. A "Locations" tab in our "Spain 2026" spreadsheet with all of our researched venues, beaches, attractions, restaurants, wine bars, rendezvous points, etc.
    - This serves as our catch-all reference for all spots we've considered going or have on our definite hit list.
    - You can find an imperfect example we used for Italy in `examples/Italy.xlsx 'Consolidated Map' tab`
    - For subsequent versions, I'd like the following columns:
        - Name: The name of the place
        - Region: e.g. Mallorca or Costa Brava
        - Neighborhood: e.g. Deia
        - Type: eg. Dinner Restaurant, Lunch Restaurant, Cafe, Wine Bar, Beach Club, etc
        - Emoji: A descriptive emoji that indicates the type of place when seen on a map.
        - Description: a description of the place, the vibe, the operating hours if applicable, and any relevant info or must-see elements of the venue.
        - Cost Range: 1 to 5 dollar signs, e.g. $$$$
        - Address: The address of the location
        - Latitude: The latitude.
        - Longitude: The longitude.
        - Google Map: The Google Map URL (can use a formula like `=HYPERLINK("https://www.google.com/maps/search/"&ENCODEURL(A1&", "Mallorca, Spain"))`)
        - References: A link to the REFERENCES.md in this repo pointing to the header referring to this particular place.
            - Each place gets its own section.
            - Record each Instagram link, Blog post URL, or AI name/conversation link as a bullet for each place, preferably with clickable links. This will make recommnedation provenance easier.
            - With each update to REFERENCES.md, please include details like the name of the source (.e.g. Gemini, Travel.com, etc.) as well as a brief blurb about what it said in regards to this spot.
        - Rating: 1-5 with 1 being "whatever" and 5 being "Must go." 5s should be used sparingly for really key events that are the top of our list.
        - Tags: Alphabetically sorted, comma separated tags, e.g. "dinner, high-end, michelin-star" or "casual lunch, outdoors, waterfront" or "beach-club, sceney". Try to reuse tags to keep things consistent, and please keep them lowercase with grouped words separated by "-".
2. A KMZ file export of this "Locations" tab that can be used to make a Google MyMaps instance (see the example in `examples/MyMap.png`).
    - This can be accomplished either using the mapitquick.com website that I made or a simple Claude skill we create (mapitquick just converts CSVs to KMZ files).
3. An "Itinerary" tab in our "Spain 2026" spreadsheet that outlines what firm plans we have for each day.
    - You can also see an example of this in `examples/Italy.xlsx 'Itinerary' tab`
    - In general, I like to have one "anchor" event per day, then allow for sponteneity or exploration.
    - This is where knowing nearby previously researched locations on the map as well as their vibe can be handy.

### Data Extraction, Structuring, and Deduplication

The following are areas I could really use your help for staying sane and organized.

I am getting recommendations from Instagram, YouTube, Blogs, and other sites. I need help with:

- Extracting the spots mentioned from LLMs, websites, reels, and videos.
    - For this, we may rely on either Manus, which has proven quite capable
    - Or we can use Apify, which has a tool or extracting instagram videos
    - Both API keys for these services are available to you.
    - We can build a skill for them based on the web docs if they turn out to be necessasry, we will discuss further if we get to this point.
- Formatting this in my standardized way for entering a new spot (see columns above for Locations tab).
    - You will likely need to use your local skills for things like geocoding latitudes and longitudes which require APIs to accomplish.
    - You'll also need to transform things like video transcriptions or metadata into the columns prescibed above.

Specifically for this part of the process, I'd like it to go like this:
- You receive a piece of data (either pasted into the chat by me, dropped into the `staging` folder by me, or pulled by you from an API/MCP).
- You save the raw data in the `staging` folder if it is not already there.
- You extract the content if necessary (e.g. an Instagram video link was provided)
- You save the content extracted from this run in the format specified for our "Locations" tab of our target Google Sheet. This should be in the form of json and not a CSV so we can let data get long. We will convert it to CSV shape in the next step. You put this json data in the `parsed/formatted` folder. You also move the file in the `staging` folder to the `parsed/raw` folder.
- You now look at the existing data in the "Locations" tab of our Google sheet.
- For each reference in our newly parsed data:
    - If a reference to it already exists, merge any new data from our recent run into the current row. This includes any updates to the description as well as appending this latest run's source the the references.
    - If a reference does not exist, simply append the new row to our Spreadsheet.
- We should also skip any sources that have already been processed.

We can create a skill or some code tools for this if necessary to simplify.

# Vacation Vibe

For reference, here is a prompt I provided to other LLMs to indicate the general vibe target of our trip:

My girlfriend and I are planning a trip to Spain from August 28th or 29th through September 11. It’s our first time in this region peninsula, and we’re prioritizing relaxation, scenic beauty, romance, and well-curated experiences over high-effort city touring. We’re New Yorkers, so we want to avoid anything that feels like a Times Square/cruise ship/tourist trap vibe — no cheap souvenir stands, no English-only menus, no tourist junk zones. That said, we’re totally fine with places that are popular or Instagrammable as long as they’re visually stunning, tasteful, and offer a genuine or luxurious experience (like a cliffside restaurant or a boutique hotel with views).

Last year we went to the Amalfi coast and visited Capri, Ravello, and Positano. We loved Ravello the most by a mile. We felt Positano was fine but too touristy and too crowded. Capri was beautiful but also a bit too tourist-heavy. Our favorite activities ended up being: Arienzo and La Fontelina beach clubs, a cooking class by Mamma Agata, impromptu wine shopping in Ravello, and taking an hike down from Ravello to Amalfi to go shopping and explore. We also are big foodies and loved the food scene.

Our first step is to come up with a plan for where to visit in these regions, and how to divide our time. We are trying to figure out which neighborhoods to stay in, logistics for attending our plans during the day, and how to travel between legs of our trip. Most importantly we are also looking for flagship events to enjoy and make sure we book things in advance. Our budget is $20k for the two weeks.

What do you suggest based on our tastes and previous travel?


# Resources
- [Google Drive Spain Folder (RO)](https://drive.google.com/drive/u/0/folders/1x6HB0PnJOh59pXSZUWEwfdzgflqyp__S)
- [Inspiration Raw Sheet (RW)](https://docs.google.com/spreadsheets/d/1L7ZT-ahqt6GCgEozHlVzfL4Ld_pmhqg-c_8bh3iRaeQ/edit?gid=1331344583#gid=1331344583) (Idea Dump)
- [Mapitquick.com](https://www.mapitquick.com/)
    - You can find the codebase here when I am working on Windows: `C:\Users\mdinu\Code\kmzconvert`
- `examples/Example Geocoder File.xlsx`: Format required for Google MyMaps conversion by Mapitquick.com
- `examples/Italy.xlsx 'Consolidated Map' tab` - An example of the sheet we used for Italy to capture all our locations (we want to improve on this format).
- `examples/MyMap.png` - An example of waht the resulting Capri map looked like after running our spreadsheet through Mapitquick.com.
- Local Python interpreter (uv) with pandas and other tools - you may add any tools you desire to the project.