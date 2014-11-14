#!/usr/bin/env python2

import urllib2, zipfile, os, re, fnmatch, sys, platform, logging, subprocess
from StringIO import StringIO

cro="38"
ser="36"
eng="2"
slo="1"

langs = [cro, ser, eng]

force=False

sub_base="http://www.podnapisi.net"
site_base="/hr/ppodnapisi/search/"
site_end="/sS/rating/sO/desc"
site_end_HD="/sOH/1/sS/rating/sO/desc"

patn = re.compile("[a-zA-Z-&]+$|[0-9]+$")
yearp = re.compile("^19[2-9][0-9]|20[0-5][0-9]$")
shows = re.compile("^.*[Ss][0-9]{2}[Ee][0-9]{2}.*$")
shows_alt = re.compile("^.*[0-9]{1,2}[Xx][0-9]{1,2}.*$")
patterns=['720p','1080p','brrip','aac', 'ac3', 'x264', 'web-dl', 'bluray', \
	'dts', 'bdrip', 'multisubs', 'webrip']
extensions=['mkv','mp4','avi']

def get_sub(url,dir,name):
	response = urllib2.urlopen(url)
	html = response.read()
	p = html.find("class=\"button big download\"")
	p = html.find("href=",p)
	q = html.find(" ",p)
	path = html[p+6:q-1]
	link=sub_base+path
	logging.debug("Got link for middle page: '" + link + "'.")
	response = urllib2.urlopen(link)
	html = response.read()
	p = html.find("location.href =")
	q = html.find(";",p)
	path = html[p+17:q-1]
	link=sub_base+path
	logging.debug("Got link for zip: '" + link + "'.")
	response = urllib2.urlopen(link)
	zip = response.read()
	try: 
		myzip = zipfile.ZipFile(StringIO(zip))
	except zipfile.BadZipfile:
		print "Server blocked us."
		logging.debug("Bad zip file: '" + zip + "'.")
		exit()

	logging.debug("zip filelist: '" + str(myzip.namelist()) + "'.")
	for subfile in myzip.namelist():
		subdata = myzip.open(subfile).read()
		ext = subfile.split(".")[-1]
		logging.debug("Extracting: '" + subfile + "'. to '" + dir + name + "." + ext + "'.")
		f = open(dir+name+"."+ext,"w")
		f.write(subdata)
		f.close()
		return

def fetch_search_html(title, year, lang, HD):
	site = site_base + "sJ/" + lang + "/sK/"
	end = site_end
	if HD:
		end = site_end_HD
	if year == "":
		link = sub_base + site + title + end
	else:
		link = sub_base + site + title + "/sY/" + year + end
	logging.debug("Searching on link (HD=" + str(HD) + "): " + link)
	response = urllib2.urlopen(link)
	html = response.read()
	return html

def get_link(title,year,lang,fps):
	html = fetch_search_html(title,year,lang,True)
	entries = parse_sub_entries(html)
	if len(entries) == 0:
		logging.debug("Entries empty for HD, trying normal search...")
		html = fetch_search_html(title,year,lang,False)
		entries = parse_sub_entries(html)
	if len(entries) == 0:
		logging.debug("Entries still empty... Returning.")
		return
	for e in entries:
		if fps and not e['fps'] == fps:
			logging.debug("Skipping entry: " + str(e) + " beacause of FPS, should be: " + fps + "." )
			continue
		logging.debug("Accepting entry: " + str(e) + ".")
		return sub_base + e['path']
	if len(entries) > 0:
		logging.debug("Couldn't find any suitable entries. Taking the first one: " + str(entries[0]))
		return sub_base + entries[0]['path']

def parse_sub_entries(data):
	entries = []
	p = 0
	p = data.find("class=\"subtitle_page_link\"",p)
	while p != -1:
		e = {}
		p = data.find("href=",p)
		q = data.find(">",p)
		e['path'] = data[p+6:q-1]

		p = data.find("<td class=\"\">",q)
		q = data.find("</",p)
		e['fps'] = data[p+13:q]

		p = data.find("rating=",q)
		q = data.find("\" ",p)
		e['rating'] = data[p+8:q]
		entries.append(e)

		p = data.find("class=\"subtitle_page_link\"",q)

	return entries

def main():
	# clearing the log file. we're not interested in old entries.
	with open('subdownload.log', 'w'):
		pass
	# opening the log
	logging.basicConfig(filename='subdownload.log',level=logging.DEBUG)

	logging.debug("Starting instance...")

	title_from_arg = False
	# if we have an argument forwarded to the app this is used as the title
	if len(sys.argv) > 1:
		logging.debug("We got the title as an argument: " + str(sys.argv[1]))
		title_from_arg = True

	files=[]

	if title_from_arg:
		files.append(sys.argv[1])
	else:
		#recursive search through all files in a directory and matching all with the
		#appropriate extension
		for root, dirnames, filenames in os.walk("."):
			for f in filenames:
				for e in extensions:
					if fnmatch.fnmatch(f,"*." + e):
						files.append(os.path.join(root,f))

	final=[]
	#filtering out shows (regex) and samples (smaller than 100MB)
	for f in files:
		if not os.path.isfile(f) or not os.path.getsize(f) < 100000000:
			final.append(f)
		else:
			logging.debug("Removing sample:" + f + " from list.")
	
	files=final

	#fetch all subs for movies to the proper directory
	for f in files:
		if os.path.dirname(f) != "":
			directory = os.path.dirname(f) + "/"
		else:
			directory = ""

		fps=None

		if os.path.isfile(f):
			# checking for FPS with exif tool. On windows it must be paced in the
			# user directory. If the FPS line is not found we take the subtitle with
			# the best ranking
			if platform.system() == 'Linux':
				exif = "exiftool " + "'" + f + "'"
			if platform.system() == 'Windows':
				exif = os.path.expanduser("~") + "\\" "exiftool.exe " + "\"" + f + "\""
				
			logging.debug("On " + platform.system() + " and checking FPS for: " + f)
			proc = subprocess.Popen(exif,shell=True,stdout=subprocess.PIPE)
			ans = proc.communicate()
			for l in ans[0].split("\n"):
				if "Video Frame Rate" in l:
					fps = l.split(":")[1].strip().replace(".",",")
					logging.debug("Found framerate: " + fps)
			if not fps:
				logging.debug("Framerate not found.")
		else:
			logging.debug("Not checking for FPS. File doesn't exist.")

		f = os.path.basename(f)

		#get name without extension
		fname = os.path.splitext(f)[0]

		#if fname.srt exists log and skip
		if os.path.isfile(directory + "/" + fname + ".srt") and not title_from_arg:
			if not force:
				logging.debug("Skipping subtitle for " + fname + ".")
				continue

		#if . is a delimiter replace it with spaces
		if not " " in fname:
			logging.debug("The delimiter is dot(.):" + fname + ".")
			name = fname.replace("."," ")
		else:
			logging.debug("The delimiter is space:" + fname + ".")
			name = fname

		show = False
		if shows.match(name) or shows_alt.match(name):
			show = True

		search_term = ""
		#create a valid search term by detecting words
		if show:
			# if the name represents a show deal with it differently
			logging.debug("This is a show: '" + name + "'.")
			for word in name.split(" "):
				if (patn.match(word) and not word.lower() in patterns) or \
					shows.match(word) or shows_alt.match(word):
					search_term = search_term + word + " "
					if shows.match(word) or shows_alt.match(word):
						search_term = search_term.strip()
						break
				else:
					search_term = search_term.strip()
					break
		else:
			logging.debug("This is a movie: '" + name + "'.")
			for word in name.split(" "):
				# if its a movie exclude patterns and year
				if patn.match(word) and not word.lower() in patterns and not yearp.match(word):
					search_term = search_term + word + " "
				else:
					search_term = search_term.strip()
					break

		year = ""
		#find year for title if it exists and if it's not a show
		if not show:
			for word in name.split(" "):
				if yearp.match(word):
					year = word.strip()
					break

		logging.debug("Final search term is: '" + search_term + "'. Year: '" + year + "'")

		found = False

		#get link for the search term and year.
		#try one language at a time which succeeds first is picked 
		#they are tried in the following order (cro, ser, eng)
		for lang in langs: 
			lin = get_link(search_term.replace(" ", "%20"),year,lang,fps)
			if lin != None:
				logging.debug("Found link: '" + lin + "'. Language: '" + lang + "'.")
				logging.debug("Directory: '" + directory + "'.")
				logging.debug("Fetching...")
				if found:
					get_sub(lin,directory,fname + "_" + lang)
				else:
					get_sub(lin,directory,fname)
					found = True
				logging.debug("Finished.")

		continue

	logging.debug("Wrapping things up...")

if __name__ == '__main__':
	main()
