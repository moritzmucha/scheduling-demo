#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
~~ Scheduling conflict solver~~

Outputs all possible combinations for your weekly schedule! 
Just provide one definition file for each subject, named subjectname.txt, 
placed inside a folder ./subjects/, and formatted the following way:

UE
Di 8:00-9:30
Do 10:00-11:30

or

VO
Mo 11:00-12:30
Di 11:00-12:30
Mi 11:00-12:00

- "UE" type subjects will be treated as requiring exactly ONE of the time slots
  listed
- "VO" subjects will strive to fill ALL the time slots (but less-than-perfect
  schedules where individual VO slots are skipped will be saved anyway)

Optional:
- location
- color for the subject's graphical representation
  (as either HTML color name or hex code or tuple of RGB values from 0-255)
e.g.:

UE
steelblue / #4682b4 / 70,130,180
Di 8:00-9:30 Audimax
Do 10:00-11:30 other place

Output will be saved in ./schedules/
"""

import sys, os, re, glob, itertools, threading
import numpy as np
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont, ImageColor
from time import sleep

in_dir_name  = "subjects"
out_dir_name = "schedules"

cleanup_at_start = True

start_of_day = 8
end_of_day   = 19
no_of_days   = 5

weekdays = [
        "Montag",
        "Dienstag",
        "Mittwoch",
        "Donnerstag",
        "Freitag",
        "Samstag",
        "Sonntag"
]
abbreviation_length = 2

text_file          = False
ascii_calendar     = False
graphical_calendar = True
cal_resolution     = (1200,740)

class Schedule:
    def __init__(self, subjects, alloc_by_subj, blank, dt_by_index):
        self.table = blank.copy()
        self.create_schedule(subjects, alloc_by_subj, dt_by_index)
    
    def create_schedule(self, subjects, alloc_by_subj, dtin):
        print("creating new schedule ...")
        
        for subject in subjects:
            for i in range(len(subject.times)):
                if alloc_by_subj[subject].enables_timeslot[i]:
                    selected_time = subject.times[i]
                    if Schedule.is_free(self.table, selected_time, dtin):
                        Schedule.fill(self.table, subject, selected_time, dtin)
                        subject.mark_allocated(selected_time)
        
        for subject in subjects:
            if subject.type == "VO":
                for selected_time in subject.times:
                    if (
                        selected_time not in subject.allocated_times and
                        Schedule.is_free(self.table, selected_time, dtin)
                    ):
                        Schedule.fill(self.table, subject, selected_time, dtin)
                        subject.mark_allocated(selected_time)
        
        self.is_incomplete = False
        self.failed        = False
        
        for subject in subjects:
            if not subject.is_partially_complete():
                self.failed = True
            elif not subject.is_complete():
                self.is_incomplete = True
            subject.reset()
        
        return self.table
    
    def __eq__(self, other):
        return self.table == other.table
    
    def empty_schedule():
        sched = dict()
        for day in range(day0, day0 + no_of_days):
            for hh in range(start_of_day, end_of_day):
                for mm in range(0, 60, 5):
                    sched[datetime(year,month,day,hh,mm)] = ""
        return sched
    
    def is_free(schedule, selected_time, dt_by_index):
        t1 = dt_by_index.index(selected_time[0])
        t2 = dt_by_index.index(selected_time[1] - timedelta(minutes=5)) + 1
        for i in range(t1, t2):
            if schedule[dt_by_index[i]]: return False
        return True
    
    def fill(schedule, subject, selected_time, dt_by_index):
        t1 = dt_by_index.index(selected_time[0])
        t2 = dt_by_index.index(selected_time[1] - timedelta(minutes=5)) + 1
        for i in range(t1, t2):
            schedule[dt_by_index[i]] = subject.name

class Subject:
    name_pattern = re.compile(r"(.+)\.txt$")
    time_loc_pattern = re.compile(
        r"^(\w+)\W?\s+(\d{1,2})[:.](\d\d)-(\d{1,2})[:.](\d\d)\W?(\s+)?(.+)?$")
    ue_pattern = re.compile(r"[Uu][Ee]")
    vo_pattern = re.compile(r"[Vv][Oo]")
    color_tuple_pattern = re.compile(
        r"^\(?(\d{1,3})\)? ?\W? ?\(?(\d{1,3})\)? ?\W? ?\(?(\d{1,3})\)?$")
    color_string_pattern = re.compile(r"(^#[\dA-Fa-f]{3,6}$|^[A-Za-z]+$)")
    weekday_patterns = list()
    for i in range(7):
        daystr = weekdays[i]
        tmp = ""
        for j in range(abbreviation_length):
            tmp += "["+daystr[j]+daystr[j].swapcase()+"]"
        pat = re.compile(tmp+"("+daystr[abbreviation_length:]+")?$")
        weekday_patterns.append(pat)
    
    def __init__(self, filename):
        self.name      = re.search(Subject.name_pattern, filename).group(1)
        self.times     = list()
        self.locations = list()
        self.type      = ""
        self.color     = (127,127,127)
        with open("./"+in_dir_name+"/"+filename, "r") as fh:
            line = fh.readline().rstrip()
            if re.search(Subject.ue_pattern, line):
                self.type = "UE"
            elif re.search(Subject.vo_pattern, line):
                self.type = "VO"
            else:
                print("\nerror: subject '"+self.name+"'doesn't have a "
                      +"recognizable type\n")
                sys.exit()
            line = fh.readline().rstrip()
            if re.search(Subject.color_tuple_pattern, line):
                cmatch = re.search(Subject.color_tuple_pattern, line)
                self.color = (int(cmatch.group(1)), int(cmatch.group(2)),
                              int(cmatch.group(3)))
                skip_reading = 0
            elif re.search(Subject.color_string_pattern, line):
                self.color = line
                skip_reading = 0
            else:
                skip_reading = 1
            n = 0
            while line:
                if n >= skip_reading:
                    line = fh.readline().rstrip()
                if line:
                    match = re.search(Subject.time_loc_pattern, line)
                    if match:
                        try:
                            day = day0 + Subject.weekday_number(match.group(1))
                        except TypeError:
                            print("\nerror: wrong weekday format at subject '"
                                  +self.name+"'\n")
                            sys.exit()
                        begh = int(match.group(2))
                        begm = int(match.group(3))
                        endh = int(match.group(4))
                        endm = int(match.group(5))
                        self.times.append((datetime(year,month,day,begh,begm),
                                           datetime(year,month,day,endh,endm)))
                        if match.group(7):
                            self.locations.append(match.group(7))
                        else:
                            self.locations.append("")
                    else:
                        print("\nerror: times/location of subject '"+self.name
                              +"' can't be read\n")
                        sys.exit()
                n += 1
        self.start_times = [element[0] for element in self.times]
        self.allocated_times = set()
    
    def mark_allocated(self, selected_time):
        self.allocated_times.add(selected_time)
    
    def is_complete(self):
        if self.type == "VO":
            return self.allocated_times == set(self.times)
        else:
            return len(self.allocated_times) >= 1
    
    def is_partially_complete(self):
        return len(self.allocated_times) >= 1
    
    def reset(self):
        self.allocated_times = set()

    def weekday_number(weekday):
        for i in range(7):
            if re.match(Subject.weekday_patterns[i], weekday): return i

class Allocation:
    def __init__(self, subject):
        self.index = 0
        self.has_reached_end = False
        tmp = itertools.product([True, False], repeat=len(subject.times))
        if subject.type == "VO":
            self.__array = [booltup for booltup in tmp if any(booltup)]
        else:
            self.__array = [booltup for booltup in tmp if sum(booltup) == 1]
    
    def get_array(self):
        return self.__array[self.index]
    
    def advance(self):
        if self.index < len(self.__array) - 1:
            self.index += 1
        else:
            self.has_reached_end = True
    
    def reverse(self):
        if self.index > 0:
            self.index -= 1
    
    def reset_end_status(self):
        self.has_reached_end = False
    
    enables_timeslot = property(get_array)

def load_subjects(subject_dir):
    filename_pattern   = re.compile(
            r"\."+slash+slash2+in_dir_name+slash+slash2+r"(.*)")
    subject_file_paths = glob.glob(subject_dir+"*.txt")
    
    if subject_file_paths:
        print("loading subject definitions from "+subject_dir+" ...")
        subject_file_names = [re.search(filename_pattern, path).group(1)
                              for path in subject_file_paths]
        subjects = [Subject(file) for file in subject_file_names]
    else:
        print("\nerror: no subject definition files found\n"
              +"please place them inside "+subject_dir+"\n")
        if not in_dir_name in local_files:
            os.popen("mkdir "+subject_dir)
        sys.exit()
    
    return subjects

def percolate(alloc_by_subj):
    for subject in alloc_by_subj:
        if alloc_by_subj[subject].has_reached_end:
            alloc_by_subj[subject].reset_end_status()
            return
    
    global permutations
    perm_check = tuple([alloc_by_subj[subject].enables_timeslot
                        for subject in alloc_by_subj])
    if perm_check in permutations:
        return
    else:
        permutations.add(perm_check)
    
    global saved_schedules, duplicates
    schedule = Schedule(subjects, alloc_by_subj, blank_schedule, dt_by_index)
    
    if schedule.failed:
        print("abandoning: failed to include all subjects\n")
    elif any([schedule == element for element in saved_schedules]):
        duplicates += 1
        print("abandoning: duplicate of existing schedule\n")
    else:
        if not schedule.is_incomplete:
            print("schedule successfully completed!")
        else:
            print("schedule created with at least one lecture incomplete")
        saved_schedules.append(schedule)
        schedule.version = saved_schedules.index(schedule) + 1
        if text_file:
            plain_write(schedule)
        if ascii_calendar:
            fancy_write(schedule)
        if graphical_calendar:
            create_graphical_calendar(schedule, subjects, *cal_resolution)
        print()
    
    for subject in alloc_by_subj:
        alloc_by_subj[subject].advance()
        percolate(alloc_by_subj)
        alloc_by_subj[subject].reverse()

def create_filename(schedule):
    if schedule.is_incomplete:
        completeness = "_INCOMPLETE_"
    else:
        completeness = ""
    return "schedule"+str(schedule.version)+completeness

def plain_write(schedule):
    schedule_dir = "./"+out_dir_name+"/"
    schedule_filename = create_filename(schedule)+".txt"
    print("saving as "+schedule_dir+schedule_filename)
    
    with open(schedule_dir + schedule_filename, "w") as fh:
        for step in schedule.table:
            fh.write(weekdays[step.weekday()][:abbreviation_length]+" "
                     +re.search(dtpat, str(step)).group(1)
                     +" "+schedule.table[step]+"\n")

def fancy_write(schedule):
    field_width  = 30
    row          = "{0:^" + str(field_width) + "s}"
    toprow       = "      "
    for i in range(no_of_days):
        toprow += "{"+str(i)+":^"+str(field_width)+"s}"
    toprow += "\n"
    
    schedule_dir = "./"+out_dir_name+"/"
    schedule_filename = create_filename(schedule)+"ascii.txt"
    print("saving as "+schedule_dir+schedule_filename)
    
    with open(schedule_dir + schedule_filename, "w") as fh:
        fh.write(toprow.format(*weekdays))
        t = datetime(year,month,day0,start_of_day)
        while t.hour < end_of_day:
            fh.write("{0:6s}".format(re.search(dtpat, str(t)).group(1)))
            d = 0
            while d < no_of_days:
                fh.write(row.format(schedule.table[t]))
                t += timedelta(days=1)
                d += 1
            fh.write("\n")
            t += timedelta(days=-no_of_days, minutes=5)

def create_graphical_calendar(schedule, subjects, res_x, res_y):
    first_column   = int(0.0583 * res_x)
    top_row        = int(0.0297 * res_y)
    celltxt_offset = (res_x//400, res_x//400)
    s1             = res_x // 80
    s2             = res_x // 100
    bg_color       = "white"
    line_color     = "#cccccc"
    labeltxt_color = "black"
    celltxt_color1 = "white"   # for dark background
    celltxt_color2 = "black"   # for light background
    
    try:
        fnt0 = ImageFont.truetype('arialbd.ttf', s1)
        fnt1 = ImageFont.truetype('arial.ttf', s1)
        fnt2 = ImageFont.truetype('arial.ttf', s2)
    except OSError:
        try:
            fnt0 = ImageFont.truetype('Pillow/Tests/fonts/FreeSansBold.ttf',s1)
            fnt1 = ImageFont.truetype('Pillow/Tests/fonts/FreeSans.ttf', s1)
            fnt2 = ImageFont.truetype('Pillow/Tests/fonts/FreeSans.ttf', s2)
        except OSError:
            fnt0 = fnt1 = fnt2 = ImageFont.load_default()
    
    img  = Image.new("RGB", (res_x, res_y), color=bg_color)
    draw = ImageDraw.Draw(img)
    
    # map x coordinates to days
    x_begofday = np.linspace(first_column, res_x, no_of_days + 1)
    
    # map y coordinates to times
    n_timeslots = 12 * (end_of_day - start_of_day)
    y_row = np.linspace(top_row, res_y, n_timeslots + 1)
    y_begoftime = {dt_by_index[i]: y_row[i] for i in range(n_timeslots)}
    y_begoftime[datetime(year, month, day0, end_of_day)] = y_row[-1]
    
    # draw horizontal lines
    for i in range(0, n_timeslots, 3):
        draw.line([(0, y_row[i]), (res_x, y_row[i])], fill = line_color)
    
    # draw vertical lines
    for i in range(no_of_days):
        draw.line([(x_begofday[i],0), (x_begofday[i],res_y)], fill=line_color)
    
    # label top row with weekdays
    day_width = (res_x - first_column) / no_of_days
    for i in range(no_of_days):
        w, h = draw.textsize(weekdays[i], font=fnt0)
        draw.text((x_begofday[i] + (day_width - w)/2, 3), weekdays[i],
                  fill=labeltxt_color, font=fnt0)
    
    # label first column with times
    t = dt_by_index[0]
    w, h = draw.textsize(re.search(dtpat, str(t)).group(1)+"-"
                         +re.search(dtpat, str(t)).group(1), font=fnt2)
    for i in range(0, n_timeslots, 3):
        t = dt_by_index[i]
        t_end = t + timedelta(minutes=15)
        time_str = re.search(dtpat, str(t)).group(1)+"-"+re.search(dtpat,
                            str(t_end)).group(1)
        x = (first_column - w)/2
        y = y_begoftime[t] + (y_begoftime[t_end] - y_begoftime[t] - h)/2
        draw.text((x,y), time_str, fill=labeltxt_color, font=fnt2)
    
    # fill calendar
    subject_dict = {subject.name: subject for subject in subjects}
    
    for step in schedule.table:
        if schedule.table[step]:
            subj_name = schedule.table[step]
            subj = subject_dict[subj_name]
            try:
                i = subj.start_times.index(step)
                subj_times = subj.times[i]
                subj_location = subj.locations[i]
                
                if type(subj.color) == str:
                    (r,g,b) = ImageColor.getrgb(subj.color)
                else:
                    (r,g,b) = subj.color
                if np.sqrt(0.299*r**2 + 0.587*g**2 + 0.114*b**2)/255 < 0.75:
                    celltxt_color = celltxt_color1
                else:
                    celltxt_color = celltxt_color2
                    
                d = step.weekday()
                rect_beg_x = x_begofday[d] + 1
                rect_beg_y = y_begoftime[subj_times[0]-timedelta(days=d)] + 1
                rect_end_x = x_begofday[d+1] - 1
                rect_end_y = y_begoftime[subj_times[1]-timedelta(days=d)] - 1
                draw.rectangle([(rect_beg_x, rect_beg_y),
                                (rect_end_x, rect_end_y)],
                               fill = subj.color)
                
                w, h = draw.textsize(subj_name, font=fnt1)
                
                if rect_end_y - rect_beg_y < 2 * (h + celltxt_offset[1]):
                    celltxto = (celltxt_offset[0], 1)
                else:
                    celltxto = celltxt_offset
                
                x = rect_beg_x + (day_width - w)/2
                y = rect_beg_y + celltxto[1] * 2/3
                draw.text((x,y), subj_name, fill=celltxt_color, font=fnt1)
                
                time_str = (
                    re.search(dtpat, str(subj_times[0])).group(1)
                    +" - "+re.search(dtpat, str(subj_times[1])).group(1)
                )
                w, h = draw.textsize(time_str, font=fnt1)
                x = rect_beg_x + celltxto[0]
                y = rect_end_y - h - celltxto[1]
                draw.text((x,y), time_str, fill=celltxt_color, font=fnt1)
                
                try:
                    w, h = draw.textsize(subj_location, font=fnt1)
                    x = rect_end_x - w - celltxto[0]
                    draw.text((x,y), subj_location, fill=celltxt_color,
                              font=fnt1)
                except SystemError:
                    pass
            
            except ValueError:
                pass
    
    schedule_dir = "./"+out_dir_name+"/"
    schedule_filename = create_filename(schedule)+".png"
    print("saving graphical calendar as "+schedule_dir+schedule_filename)
    img.save(schedule_dir+schedule_filename)
    
    global calendars_shown
    if calendars_shown < 1:
        prev_stack_size = threading.stack_size()
        displaythread = threading.Thread(target=display_calendar, args=(img,))
        displaythread.start()
        calendars_shown += 1
        threading.stack_size(prev_stack_size)

def display_calendar(image):
    image.show()

if os.name == "nt":
    slash = "\\"
    slash2 = slash
    delcmd = "del /q"
else:
    slash = "/"
    slash2 = ""
    delcmd = "rm -f"

dtpat = re.compile(r"\d\d-\d\d-\d\d (\d\d:\d\d):\d\d")
year  = 2017
month = 10
day0  = 2

local_files  = glob.glob("*")
subject_dir  = "." + slash + in_dir_name  + slash
schedule_dir = "." + slash + out_dir_name + slash
subjects     = load_subjects(subject_dir)

if out_dir_name in local_files:
    if cleanup_at_start:
        print("cleaning up in "+schedule_dir+" ...\n")
        os.popen(delcmd+" "+schedule_dir+"*")
else:
    print("creating schedule directory under "+schedule_dir+" ...\n")
    os.popen("mkdir "+schedule_dir)

sleep(0.8)

saved_schedules = list()
permutations    = set()
duplicates      = 0
calendars_shown = 0
blank_schedule  = Schedule.empty_schedule()
dt_by_index     = sorted(blank_schedule.keys())
alloc_by_subj   = {subject: Allocation(subject) for subject in subjects}

custom_stack_size = 256 * 2**20 -1 # 256 MiB = Windows limit
custom_rec_limit  = 300000         # empirical max: 91162 at  64 MiB stack size
                                                 # 182343 at 128 MiB
threading.stack_size(custom_stack_size)          # 167611 at 128 MiB
old_rec_limit = sys.getrecursionlimit()          # 335379 at 256 MiB
sys.setrecursionlimit(custom_rec_limit)
thread = threading.Thread(target = percolate, args = (alloc_by_subj,))
thread.start()
thread.join()
sleep(0.2)
sys.setrecursionlimit(old_rec_limit)
threading.stack_size()

incompletes = 0
for schedule in saved_schedules:
    if schedule.is_incomplete:
        incompletes += 1

n = len(saved_schedules)
if n == 1:
    sched_str = "schedule"
else:
    sched_str = "schedules"
if duplicates == 1:
    dupl_str = "duplicate"
else:
    dupl_str = "duplicates"
print("created "+str(n)+" "+sched_str+", of which "+str(incompletes)
      +" incomplete (plus "+str(duplicates)+" "+dupl_str+")")
