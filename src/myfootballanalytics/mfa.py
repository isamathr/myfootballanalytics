from bs4 import BeautifulSoup
import concurrent.futures
import multiprocessing
import json
import pandas as pd
import requests
import os
import math
import datetime
import time
from tqdm.notebook import tqdm as tqdm_nb
from sys import exit
import shutil
import matplotlib.pyplot as plt
from mplsoccer.pitch import Pitch
import numpy as np
import statistics
#from understatapi import UnderstatClient

## Author: Ilias Samathrakis

## Class to scrape and save football data from https://understat.com/

class DataUpdater:
    def __init__(self,leagues,seasons,save_dir_path=os.getcwd(),save_csv_file=False):
        self.leagues = leagues
        self.seasons = seasons
        self.save_dir_path = save_dir_path
        self.dir_name = "Football_Data"
        self.ids_file = "league_ids.dat"
        self.years = []
        self.save_csv_file = save_csv_file
        for i in self.seasons:
            self.years.append(int(i[:4]))
        self.update_data()
    
    def __check_seasons(self):
        for i in range(len(self.seasons)):
            f = self.seasons[i].split("-")
            if len(f) > 2:
                exit("Invalid format for 'seasons'. Check it out")
            for j in range(len(f)):
                if f[j].isdigit() == False or f[j].isdigit() == False:
                    exit("'seasons' contains non digit characters")
                if int(f[j]) < 2014:
                    exit("Data unavailable before 2014")
                if int(f[1]) - int(f[0]) != 1:
                    exit("'seasons' cannot differ more than one. Modify")
    
    def __check_leagues(self):
        available = ["Ligue1", "PremierLeague", "Bundesliga", "LaLiga", "SerieA"]
        for i in range(len(self.leagues)):
            if self.leagues[i] not in available:
                exit("Unavailable league. Please modify")
    
    def __create_tree(self):
        os.makedirs(os.path.join(self.save_dir_path, self.dir_name), exist_ok=True)
        ## Creates directory for each league and year
        for i in range(len(self.leagues)):
            if not os.path.exists(os.path.join(self.save_dir_path, self.dir_name, self.leagues[i])):
                os.makedirs(os.path.join(self.save_dir_path, self.dir_name, self.leagues[i]), exist_ok=True)
            for j in range(len(self.years)):
                if os.path.exists(os.path.join(self.save_dir_path, self.dir_name, self.leagues[i], str(self.seasons[j]))):
                    shutil.rmtree(os.path.join(self.save_dir_path, self.dir_name, self.leagues[i], str(self.seasons[j])))
                os.makedirs(os.path.join(self.save_dir_path, self.dir_name, self.leagues[i], str(self.seasons[j])), exist_ok=True)
                    
    def __ids(self):
        match_ids = [[] for _ in self.leagues]
        filename = os.path.join(self.save_dir_path,self.ids_file)
        with open(filename, 'r') as rf:
            for line in rf:
                name, season, ids_str = line.split(":")
                name = name.strip()
                season = season.strip()
                if (name in self.leagues) and (season in self.seasons):
                    ids = []
                    for item in ids_str.split():
                        if '-' in item:
                            start, end = map(int, item.split('-'))
                            ids += list(range(start, end+1))
                        else:
                            ids.append(int(item))
                    match_ids[self.leagues.index(name)].append(ids)
        return match_ids
    
    def __check_file(self,league,season,index):
        filename = os.path.join(self.save_dir_path, self.dir_name, league, season, str(index) + ".dat")
        return os.path.isfile(filename)
    
    def __scrape_data(self,match_id,index):
        base_url = "https://understat.com/match/"
        try:
            url = base_url + match_id
            res = requests.get(url)
            soup = BeautifulSoup(res.content,"lxml")
            scripts = soup.find_all("script")
            strings = scripts[index].string
            ind_start = strings.index("('")+2
            ind_end = strings.index("')")
            json_data = strings[ind_start:ind_end]
            json_data = json_data.encode('utf8').decode('unicode_escape')
            data = json.loads(json_data)
        except:
            data = []
        return data
    
    #def __extract_data_api(self,match_id):
    #    data = UnderstatClient().match(match=str(match_id)).get_shot_data()
    #    return data
    
    def __create_json_file(self,data,league,season,index):
        filename = os.path.join(self.save_dir_path, self.dir_name, league, season, str(index) + ".json")
        data = data.reset_index()
        data.to_json(filename,indent=4)
        
    def __save_csv_file(self,data,league,season):
        pitch_x = 95.65
        pitch_y = 70.00

        data['league'] = str(league)

        Xmod = data.X.astype('float') * pitch_x
        Ymod = data.Y.astype('float') * pitch_y

        imp_team = data.h_team

        data['Xmod'] = Xmod.where(data.h_a=="h", other=(1-data.X.astype('float')) * pitch_x)
        data['Ymod'] = Ymod.where(data.h_a=="h", other=(1-data.Y.astype('float')) * pitch_y)

        data['important_team'] = imp_team.where(data.h_a=='h',other=data.a_team)
        data['F/A'] = 'For'

        part = data.copy()
        part['important_team'] = part.apply(lambda x: x['h_team'] if x['important_team'] == x['a_team'] else x['a_team'], axis=1)
        part['F/A'] = 'Against'
        result = pd.concat([data, part], ignore_index=True)
        
        file_name = league + "_" + season + ".csv"
        result[['result','Xmod','Ymod','xG','player','h_a','situation','season','match_id',
            'h_team','a_team','h_goals','a_goals','important_team','league','F/A']].to_csv(os.path.join(self.save_dir_path,self.dir_name,file_name),encoding='utf-8-sig')
        
    
    def update_data(self): 
        self.__check_seasons()
        self.__check_leagues()
        self.__create_tree()
        match_ids = self.__ids()
        for i in tqdm_nb(range(len(self.leagues)),desc='League'):
            d = pd.DataFrame()
            for j in tqdm_nb(range(len(self.seasons)),desc='Seasons',leave=False):
                d = pd.DataFrame()
                for k in tqdm_nb(range(len(match_ids[i][j])),desc='Matches',leave=False):
                    index = match_ids[i][j].index(match_ids[i][j][k]) + 1
                    condition = self.__check_file(self.leagues[i],self.seasons[j],index)
                    if condition == False:
                        data = self.__scrape_data(str(match_ids[i][j][k]),1) ## scrape data from understat.com
                        #data = self.__extract_data_api(match_ids[i][j][k])    ## extract data using understatapi
                        time.sleep(0.1)
                        if 'h' in data:
                            df1 = pd.json_normalize(data, record_path=['h'])
                        if 'a' in data:
                            df2 = pd.json_normalize(data, record_path=['a'])
                        df = pd.concat([df1,df2])
                        df_full = pd.concat([d,df])
                        d = df_full
                        self.__create_json_file(df,self.leagues[i],self.seasons[j],index)
                if self.save_csv_file:
                    self.__save_csv_file(df_full,self.leagues[i],self.seasons[j])

## Class to Find IDs of matches
                    
class FindIDs:
    def __init__(self,parallel,save_dir_path=os.getcwd()):
        self.save_dir_path = save_dir_path
        self.parallel = parallel
        self.findids()
        
    def __boundaries(self):
        min_number = 1
        max_number = 21000
        index = []
        for i in range(min_number,max_number):
            index.append(str(i))
        return index
            
    def __determine_years(self):
        min_year = 2014
        today = datetime.date.today()
        if today.month >= 8:
            max_year = today.year
        else:
            max_year = today.year - 1
        return min_year, max_year
    
    def __scrape_data(self,match_id,index):
        base_url = "https://understat.com/match/"
        try:
            url = base_url + match_id
            res = requests.get(url)
            soup = BeautifulSoup(res.content,"lxml")
            scripts = soup.find_all("script")
            strings = scripts[index].string
            ind_start = strings.index("('")+2
            ind_end = strings.index("')")
            json_data = strings[ind_start:ind_end]
            json_data = json_data.encode('utf8').decode('unicode_escape')
            data = json.loads(json_data)
            if data['h'] == []:
                first_record = data['a'][0]
            else:
                first_record = data['h'][0]
            df = pd.json_normalize(first_record)
        except:
            return None
        return df
    
    def __read_file(self):
        obj = CheckFile() 
        data = obj.get_data()
        return data
    
    def __modify_dataframe(self,matches,teams_leagues,min_year,max_year):
        l = list(set(teams_leagues.values()))
        y = [str(i) for i in range(min_year,max_year+1)]
        
        h = matches['h_team'].tolist()
        a = matches['a_team'].tolist()
        teams = h + a
        teams = list(set(teams))
        
        leagues = []
        for i in range(len(h)):
            if h[i] not in teams_leagues.keys():
                exit(f"Team '{h[i]}' does not exist. Please update file 'teams_dict.json'")
            leagues.append(teams_leagues[h[i]])
        matches['league'] = leagues
        
        ids = []
        for i in range(len(l)):
            f = []
            for j in range(len(y)):
                m = matches[(matches['season'] == y[j]) & (matches['league'] == l[i])]
                f.append(m['match_id'].tolist())
            ids.append(f)
        return ids, l, y
            
    def __create_file(self,ids,leagues,years):
        if not os.path.exists(self.save_dir_path):
            os.makedirs(self.save_dir_path, exist_ok=True)
        
        filename = os.path.join(self.save_dir_path,"league_ids.dat")
        with open(filename,'w') as wf:
            for i in range(len(leagues)):
                for j in range(len(years)):
                    strids = ""
                    for k in range(len(ids[i][j])):
                        strids = strids + " " + str(ids[i][j][k])
                    wf.write("{}: {}-{}: {}\n".format(leagues[i],years[j],str(int(years[j])+1),strids))
    
    def findids(self):
        index = self.__boundaries()
        dfs = []
        
        if self.parallel == True:
            num_cpus = multiprocessing.cpu_count()
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=num_cpus) as executor:
                results = [executor.submit(self.__scrape_data, index[i], 1) for i in range(len(index))]
                for future in tqdm_nb(concurrent.futures.as_completed(results),total=len(index)):
                    try:
                        dfs.append(future.result())
                    except:
                        exit("Error in multithreading")
        else:
            for i in tqdm_nb(range(len(index)),desc="IDs"):
                dfs.append(self.__scrape_data(index[i],1))
        
        number_none = 0
        for i in range(len(dfs)):
            if dfs[i] is None:
                number_none += 1
        
        if number_none == len(dfs):
            exit("The specified IDs do not contain matches")
        
        df2 = pd.concat(dfs,ignore_index=True)
        
        teams_leagues = self.__read_file()
        matches = df2[['match_id','season','h_team','a_team']]
        min_year, max_year = self.__determine_years()
        ids, leagues, years = self.__modify_dataframe(matches,teams_leagues,min_year,max_year)
        self.__create_file(ids,leagues,years)

## Class to load data from a specific match

class MatchDataLoader:
    def __init__(self,home_team,away_team,season,save_dir_path=os.getcwd()):
        self.home_team = home_team
        self.away_team = away_team
        self.season = season
        self.save_dir_path = save_dir_path
        self.dir_name = "Football_Data"
        #self.load_match_data()
    
    def __check_season(self):
        f = self.season.split("-")
        if len(f) > 2:
            exit("Invalid format for 'seasons'. Check it out")
        for j in range(len(f)):
            if f[j].isdigit() == False or f[j].isdigit() == False:
                exit("'seasons' contains non digit characters")
            if int(f[j]) < 2014:
                exit("Data unavailable before 2014")
            if int(f[1]) - int(f[0]) != 1:
                exit("'seasons' cannot differ more than one. Modify")
    
    def __find_match_id(self,match_path):
        files = [f for f in os.listdir(match_path) if f.endswith('.json')]
        for i in range(len(files)):
            fullpath = os.path.join(match_path,files[i])
            df = pd.read_json(fullpath)
            if (df['h_team'] == self.home_team).any() and (df['a_team'] == self.away_team).any():
                return df
        return pd.DataFrame()
    
    def __team_existance(self,l):
        h, a = False, False
        if self.home_team in l.keys():
            h = True
        if self.away_team in l.keys():
            a = True
        return h, a
    
    def __check_conditions(self,h,a):
        if h == False and a == False:
            exit("Both home and away teams are not found. Make sure they are spelled properly")
        if h == False:
            exit("Home team is not found. Make sure it is spelled correctly")
        if a == False:
            exit("Away team is not found. Make sure it is spelled correctly")
    
    def load_match_data(self):
        script_directory = os.path.dirname(os.path.abspath(__file__))
        if not os.path.exists(os.path.join(script_directory,"teams_dict.json")):
            exit("File 'teams_dict.json' does not exist.")
        with open(os.path.join(script_directory,"teams_dict.json")) as rf:
            t = json.load(rf)
        h,a = self.__team_existance(t)
        self.__check_conditions(h,a)
        
        if t[self.home_team]==t[self.away_team]:
            self.league = t[self.home_team]
        else:
            exit("The teams do not play in the same league")
        
        match_path = os.path.join(self.save_dir_path,self.dir_name,self.league,self.season)
        self.__check_season()
        df = self.__find_match_id(match_path)
        if df.empty:
            return None
        return df

## Class to analyze the data of a specific match

class MatchAnalyzer:
    def __init__(self,data):
        self.data = data
        if self.data is not None:
            self.pitch_x = 95.65
            self.pitch_y = 70.00
            self.pitch = Pitch(pitch_type="custom", pitch_color='grass', line_color='white', stripe=True, pitch_length=self.pitch_x, pitch_width=self.pitch_y)
            self.fig, self.ax = self.pitch.draw()
        #self.analyze_match()
    
    def __modify_dataframe(self,df):
        df['important_team'] = np.where(df['h_a'] == 'h', df['h_team'], df['a_team'])
        df = df[['season','h_team','a_team','h_goals','a_goals','situation','match_id','result','player','X','Y','xG','important_team']]
        return df
        
    def __draw_shots(self,df,team,color,specifier):
        team_events = df.loc[df['important_team']==team]
        if team_events.empty:
            if specifier == 'home':
                self.ax.text(2,5,df['h_team'].astype(str).tolist()[0] + " : " + df['h_goals'].astype(str).tolist()[0],c=color,fontsize=14)
                self.ax.text(2,10,"xG: 0.000",c=color,fontsize=14)
                t = df['h_team'].astype(str).tolist()[0]
            if specifier == 'away':
                self.ax.text(62,5,df['a_team'].astype(str).tolist()[0] +" : " + df['a_goals'].astype(str).tolist()[0],c=color,fontsize=14)
                self.ax.text(62,10,"xG: 0.000",c=color,fontsize=14)
                t = df['a_team'].astype(str).tolist()[0]
            return 0, 0, 0, 0, 0, t
        
        goal = team_events.loc[team_events['result']=='Goal']
        nogoal = team_events.loc[team_events['result']!='Goal']
        xGgoal = goal['xG'].astype(float) * self.pitch_x
        xGnogoal = nogoal['xG'].astype(float) * self.pitch_x

        total_xG = round(team_events['xG'].sum(),3)
        mean_xG = round(team_events['xG'].mean(),3)
        chances = len(team_events)
        big_chances = len(team_events[team_events['xG'] > 0.3]['xG'])
        
        if team.tolist()[0] == team_events['h_team'].tolist()[0]:
            self.ax.scatter(goal['X'].astype(float)*self.pitch_x,goal['Y'].astype(float)*self.pitch_y,c=color,s=xGgoal,marker=(5,2))
            self.ax.scatter(nogoal['X'].astype(float)*self.pitch_x,nogoal['Y'].astype(float)*self.pitch_y,s=xGnogoal,facecolors='none',edgecolors=color,marker='o')
            self.ax.text(2,self.pitch_y-5,team_events['important_team'].astype(str).tolist()[0] + " : " + team_events['h_goals'].astype(str).tolist()[0],c=color,fontsize=14)
            self.ax.text(2,self.pitch_y-10,"xG: " + str(total_xG),c=color,fontsize=14)
            t = team.tolist()[0]
            penalty_area = len(team_events[(team_events['X'].astype(float)*self.pitch_x >= self.pitch_x-16.5) & (team_events['Y'].astype(float)*self.pitch_y >= 15.0) & (team_events['Y'].astype(float)*self.pitch_y <= 55.00)])
        elif team.tolist()[0] == team_events['a_team'].tolist()[0]:
            self.ax.scatter((1-goal['X'].astype(float))*self.pitch_x,(1-goal['Y'].astype(float))*self.pitch_y,c=color,s=xGgoal,marker=(5,2))
            self.ax.scatter((1-nogoal['X'].astype(float))*self.pitch_x,(1-nogoal['Y'].astype(float))*self.pitch_y,s=xGnogoal,facecolors='none', edgecolors=color,marker='o')
            self.ax.text(self.pitch_x/2+2,self.pitch_y-5,team_events['important_team'].astype(str).tolist()[0] +" : " + team_events['a_goals'].astype(str).tolist()[0],c=color,fontsize=14)
            self.ax.text(self.pitch_x/2+2,self.pitch_y-10,"xG: " + str(total_xG),c=color,fontsize=14)
            t = team.tolist()[0]
            penalty_area = len(team_events[((1-team_events['X'].astype(float))*self.pitch_x <= 16.5) & ((1-team_events['Y'].astype(float))*self.pitch_y >= 15.0) & ((1-team_events['Y'].astype(float))*self.pitch_y <= 55.00)])
        return total_xG, mean_xG, chances, big_chances, penalty_area, t
    
    def __data_table(self,total_xG_h,mean_xG_h,chances_h,big_chances_h,penalty_area_h,h_team,total_xG_a,mean_xG_a,chances_a,big_chances_a,penalty_area_a,a_team):
        data_dict = { '' : ['Total xG','xG per chance','Number of chances','Number of big chances','Chances within the box'],
            h_team : [total_xG_h, mean_xG_h, chances_h, big_chances_h, penalty_area_h],
            a_team : [total_xG_a, mean_xG_a, chances_a, big_chances_a, penalty_area_a]}
        
        data = pd.DataFrame(data_dict)
        data = data.set_index('')
        return data
    
    def analyze_match(self):
        if self.data is None:
            exit("Match not found. Make sure that the names of the teams are spelled correctly. \nIt is also possible that the match has not started yet.")
        df = self.__modify_dataframe(self.data)
        total_xG_h, mean_xG_h, chances_h, big_chances_h, penalty_area_h, h_team = self.__draw_shots(df,df['h_team'],'blue','home')
        total_xG_a, mean_xG_a, chances_a, big_chances_a, penalty_area_a, a_team = self.__draw_shots(df,df['a_team'],'red','away')
        table = self.__data_table(total_xG_h, mean_xG_h, chances_h, big_chances_h, penalty_area_h, h_team,total_xG_a, mean_xG_a, chances_a, big_chances_a, penalty_area_a, a_team)
        return table

## Class to analyze all the matches of a league

class LeagueAnalyzer:
    def __init__(self,league,seasons,save_dir_path=os.getcwd(),save_players_csv=False):
        self.league = league
        self.seasons = seasons
        self.save_dir_path = save_dir_path
        self.dir_name = "Football_Data"
        self.save_players_csv = save_players_csv
        self.analyze_league()
    
    def __check_league(self):
        available = ["Ligue1", "PremierLeague", "Bundesliga", "LaLiga", "SerieA"]
        if self.league not in available:
            exit("Unavailable league. Please modify")
    
    def __check_seasons(self):
        for i in range(len(self.seasons)):
            f = self.seasons[i].split("-")
            if len(f) > 2:
                exit("Invalid format for 'seasons'. Check it out")
            for j in range(len(f)):
                if f[j].isdigit() == False or f[j].isdigit() == False:
                    exit("'seasons' contains non digit characters")
                if int(f[j]) < 2014:
                    exit("Data unavailable before 2014")
                if int(f[1]) - int(f[0]) != 1:
                    exit("'seasons' cannot differ more than one. Modify")
    
    def __load_data(self,match_path):
        files = [f for f in os.listdir(match_path) if f.endswith('.json')]
        df = pd.DataFrame()
        for i in range(len(files)):
            fullpath = os.path.join(match_path,files[i])
            df_new = pd.read_json(fullpath)
            data = pd.concat([df,df_new],ignore_index=True)
            df = data
        return data
    
    def __modify_dataframe(self,df):
        df['important_team'] = np.where(df['h_a'] == 'h', df['h_team'], df['a_team']) ## Add the name of the team performed the action
        return df
    
    def __find_teams(self,df):
        home_teams = df['h_team'].tolist()
        away_teams = df['a_team'].tolist()
        teams = home_teams + away_teams 
        teams = list(set(teams))
        return teams
    
    def __find_matches(self,df,teams):
        number = []
        for i in range(len(teams)):
            df_home_matches = df[df['h_team']==teams[i]]['a_team']
            home_matches = df_home_matches.tolist()
            df_away_matches = df[df['a_team']==teams[i]]['h_team']
            away_matches = df_away_matches.tolist()
            matches = len(list(set(home_matches))+ list(set(away_matches)))
            number.append(matches)
        return number
    
    def __add_data(self,df):
        df['F/A'] = ['For'] * len(df)
        part = df.copy()
        part['important_team'] = part.apply(lambda x: x['h_team'] if x['important_team'] == x['a_team'] else x['a_team'], axis=1)
        part['F/A'] = 'Against'
        result = pd.concat([df, part], ignore_index=True)
        return result
    
    def __sort_list_rev(self,mylistA, mylistB):
        s_A = sorted(mylistA,reverse=True)
        s_B = [i for _, i in sorted(zip(mylistA,mylistB),reverse=True)]
        return s_A, s_B
        
    def __plot_figs(self,s,teams,matches):
        xG_for, xG_ag = [], []
        team_xG_for_game, team_xG_ag_game = [], []
        for i in range(len(teams)):
            t1, t2 = [], []
            for j in range(len(teams)):
                if teams[i] != teams[j]:
                    a1 = self.data[(self.data['important_team'] == teams[i]) & (self.data['a_team'] == teams[j]) & (self.data['F/A'] == 'For') & (self.data['situation'] == "OpenPlay")]
                    a2 = self.data[(self.data['important_team'] == teams[i]) & (self.data['h_team'] == teams[j]) & (self.data['F/A'] == 'For') & (self.data['situation'] == "OpenPlay")]
                    a3 = self.data[(self.data['important_team'] == teams[i]) & (self.data['a_team'] == teams[j]) & (self.data['F/A'] == 'Against') & (self.data['situation'] == "OpenPlay")]
                    a4 = self.data[(self.data['important_team'] == teams[i]) & (self.data['h_team'] == teams[j]) & (self.data['F/A'] == 'Against') & (self.data['situation'] == "OpenPlay")]
                    t1.append(round(a1['xG'].sum(),3))
                    t1.append(round(a2['xG'].sum(),3))
                    t2.append(round(a3['xG'].sum(),3))
                    t2.append(round(a4['xG'].sum(),3))
            team_xG_for_game.append(t1) 
            team_xG_ag_game.append(t2)
            t_f = self.data[(self.data['important_team'] == teams[i]) & (self.data['F/A'] == 'For')]
            t_a = self.data[(self.data['important_team'] == teams[i]) & (self.data['F/A'] == 'Against')]
            xg_for_t = t_f['xG'].sum()/matches[i]
            xg_ag_t = t_a['xG'].sum()/matches[i]
            xG_for.append(round(xg_for_t,3))     ## Average xG-for of each team
            xG_ag.append(round(xg_ag_t,3))       ## Average xG-ag  of each team
        
        avg_xG_for = sum(xG_for)/len(xG_for) ## Average xG-for of league
        avg_xG_ag = sum(xG_ag)/len(xG_ag)    ## Average xG-ag  of league
        
        fig1, ax = plt.subplots()
        ax.scatter(xG_for,xG_ag)
        ax.axhline(avg_xG_ag,linestyle='--')
        ax.axvline(avg_xG_for,linestyle='--')
        ax.set_xlabel("Average xG-for per match")
        ax.set_ylabel("Average xG-against per match")
        ax.set_title(self.league + ": " + s)
        for i, txt in enumerate(teams):
            ax.annotate(txt,(xG_for[i],xG_ag[i]),fontsize=8)
        
        avg_xG_diff = [xG_for[i]-xG_ag[i] for i in range(len(xG_for))]  ## Average xG difference of each team
        
        med_xG_for, med_xG_ag = [], []
        for i in range(len(teams)):
            med_xG_for.append(statistics.median(team_xG_for_game[i]))
            med_xG_ag.append(statistics.median(team_xG_ag_game[i]))
        
        med_xG_diff = []
        for i in range(len(med_xG_for)):
            med_xG_diff.append(round(med_xG_for[i]-med_xG_ag[i],3))
        
        xG_diff = []
        for i in range(len(team_xG_for_game)):
            f = []
            for j in range(len(team_xG_for_game[i])):
                f.append(team_xG_for_game[i][j] - team_xG_ag_game[i][j])
            xG_diff.append(f)
        
        players = list(set(self.data['player'].tolist()))
        total_xg, goals_scored, xg_g, xg_ng = [], [], [], []
        
        for i in range(len(players)):
            total_xg.append(self.data[(self.data['player']==players[i]) & (self.data['F/A']=='For')]['xG'].sum())
            goals_scored.append(len(self.data[(self.data['player']==players[i]) & (self.data['result']=='Goal') & (self.data['F/A']=='For')]))
            xg_g.append(self.data[(self.data['player']==players[i]) & (self.data['result']=='Goal') & (self.data['F/A']=='For')]['xG'].sum())
            xg_ng.append(self.data[(self.data['player']==players[i]) & (self.data['result']!='Goal') & (self.data['F/A']=='For')]['xG'].sum())
        
        mydf = pd.DataFrame(list(zip(players,total_xg,goals_scored,xg_g,xg_ng)),columns=['player','total_xG','goals','xG_scored','xG_missed'])
        players_data = mydf.sort_values(by=['xG_missed'],ascending=False)
        print(f"------------ {self.league}: {s} ------------")
        print(players_data[['player','total_xG','goals','xG_scored','xG_missed']].head(20).to_string(index=False))
        print("\n")
        
        if self.save_players_csv:
            file_name = "players_" + self.league + "_" + str(s) + ".csv"
            players_data[['player','total_xG','goals','xG_scored','xG_missed']].to_csv(os.path.join(self.save_dir_path,self.dir_name,file_name),index=False,encoding='utf-8-sig')
        
        fig2, (ax1, ax2) = plt.subplots(2,1,figsize=(15,15))
        fig2.tight_layout(h_pad=12)
        
        s_avg, s_teams_avg = self.__sort_list_rev(avg_xG_diff,teams)
        
        b1 = ax1.bar(s_teams_avg,s_avg,color='blue')
        
        ax1.set_title(self.league + ": " + s)
        ax1.set_xticklabels(s_teams_avg, rotation=90)
        ax1.set_ylabel("Average xG difference per match")
        ax1.bar_label(b1,fontsize=8)
        ax1.set_xticklabels(s_teams_avg, rotation=90)
        ax1.set_ylabel("Average xG difference per match")
        
        s_med_diff, s_teams_med_diff = self.__sort_list_rev(med_xG_diff,teams)
        
        b2 = ax2.bar(s_teams_med_diff,s_med_diff,color='blue')
        
        ax2.bar_label(b2,fontsize=8)
        ax2.set_title(self.league + ": " + s)
        ax2.set_xticklabels(s_teams_med_diff, rotation=90)
        ax2.set_ylabel("Median xG-diff per match")
        
    def analyze_league(self):
        df = pd.DataFrame()
        self.__check_seasons()
        self.__check_league()
        for i in range(len(self.seasons)):
            match_path = os.path.join(self.save_dir_path,self.dir_name,self.league,self.seasons[i])
            df_new = self.__load_data(match_path)
            teams = self.__find_teams(df_new)
            matches = self.__find_matches(df_new,teams)
            df_new = self.__modify_dataframe(df_new)
            df_new = self.__add_data(df_new)
            self.data = pd.concat([df,df_new],ignore_index=True)
            self.__plot_figs(self.seasons[i],teams,matches) 

## Class to load data from all matches of a team 

class TeamDataLoader:
    def __init__(self,seasons,team,save_dir_path=os.getcwd()):
        self.seasons = seasons
        self.team = team
        self.save_dir_path = save_dir_path
        self.dir_name = "Football_Data"
        self.load_team_data()
    
    def __check_seasons(self):
        for i in range(len(self.seasons)):
            f = self.seasons[i].split("-")
            if len(f) > 2:
                exit("Invalid format for 'seasons'. Check it out")
            for j in range(len(f)):
                if f[j].isdigit() == False or f[j].isdigit() == False:
                    exit("'seasons' contains non digit characters")
                if int(f[j]) < 2014:
                    exit("Data unavailable before 2014")
                if int(f[1]) - int(f[0]) != 1:
                    exit("'seasons' cannot differ more than one. Modify")
    
    def __find_team_league(self):
        obj = CheckFile() 
        data = obj.get_data()
        return data[self.team]
    
    def __read_files(self,path):
        files = [f for f in os.listdir(path) if f.endswith('.json')]
        df = pd.DataFrame()
        for i in range(len(files)):
            fullpath = os.path.join(path,files[i])
            df_all = pd.read_json(fullpath)
            if (df_all['h_team'] == self.team).any() or (df_all['a_team'] == self.team).any():
                df_team = pd.concat([df,df_all])
                df = df_team
        return df_team
    
    def __modify_dataframe(self,df):
        df['important_team'] = np.where(df['h_a'] == 'h', df['h_team'], df['a_team']) ## Add the name of the team performed the action
        return df
    
    def __add_data(self,df):
        df['F/A'] = ['For'] * len(df)
        part = df.copy()
        part['important_team'] = part.apply(lambda x: x['h_team'] if x['important_team'] == x['a_team'] else x['a_team'], axis=1)
        part['F/A'] = 'Against'
        result = pd.concat([df, part], ignore_index=True)
        return result
    
    def load_team_data(self):
        league = self.__find_team_league()
        self.__check_seasons()
        d = pd.DataFrame()
        for i in range(len(self.seasons)):
            path = os.path.join(self.save_dir_path,self.dir_name,league,self.seasons[i])
            df = self.__read_files(path)
            df_t = pd.concat([d,df])
            d = df_t
        
        df_t1 = self.__modify_dataframe(df_t)
        df_team = self.__add_data(df_t1)
        return df_team

## Class to analyze data from all matches of a team
         
class TeamAnalyzer:
    def __init__(self,data,seasons,team):
        self.seasons = seasons
        self.team = team
        self.data = data
        #self.analyze_team()
    
    def __check_seasons(self):
        for i in range(len(self.seasons)):
            f = self.seasons[i].split("-")
            if len(f) > 2:
                exit("Invalid format for 'seasons'. Check it out")
            for j in range(len(f)):
                if f[j].isdigit() == False or f[j].isdigit() == False:
                    exit("'seasons' contains non digit characters")
                if int(f[j]) < 2014:
                    exit("Data unavailable before 2014")
                if int(f[1]) - int(f[0]) != 1:
                    exit("'seasons' cannot differ more than one. Modify")
    
    def __find_values(self,i):
        year = self.seasons[i][0:4]
        df_for = self.data[(self.data['season'] == int(year)) & (self.data['F/A'] == 'For') & (self.data['important_team'] == self.team) & (self.data['situation'] == "OpenPlay")]
        df_ag = self.data[(self.data['season'] == int(year)) & (self.data['F/A'] == 'Against') & (self.data['important_team'] == self.team) & (self.data['situation'] == "OpenPlay")]
        indices = list(set(df_for['match_id'].tolist()))
        num_1 = len(indices)
        num_2 = len(list(set(df_ag['match_id'].tolist())))
        index = max(num_1,num_2)
        
        avg_xG_for = round(df_for['xG'].sum()/index,3)
        avg_xG_ag = round(df_ag['xG'].sum()/index,3)
        
        xG_for_per_match, xG_ag_per_match, big_chances_for, big_chances_ag, dist_for_x, dist_for_y, dist_ag_x, dist_ag_y = [], [], [], [], [], [], [], []
        for i in range(len(indices)):
            xG_for_per_match.append(df_for[(df_for['important_team'] == self.team) & (df_for['match_id'] == indices[i]) & (df_for['F/A'] == 'For') & (df_for['situation'] == "OpenPlay")]['xG'].sum())
            xG_ag_per_match.append(df_ag[(df_ag['important_team'] == self.team) & (df_ag['match_id'] == indices[i]) & (df_ag['F/A'] == 'Against') & (df_ag['situation'] == "OpenPlay")]['xG'].sum())
            big_chances_for.append(df_for[(df_for['important_team'] == self.team) & (df_for['match_id'] == indices[i]) & (df_for['F/A'] == 'For') & (df_for['xG'] >= 0.4) & (df_for['situation'] == "OpenPlay")]['xG'].tolist())
            big_chances_ag.append(df_ag[(df_ag['important_team'] == self.team) & (df_ag['match_id'] == indices[i]) & (df_ag['F/A'] == 'Against') & (df_ag['xG'] >= 0.4) & (df_ag['situation'] == "OpenPlay")]['xG'].tolist())
            
            dist_for_x.append(df_for[(df_for['important_team'] == self.team) & (df_for['match_id'] == indices[i]) & (df_for['F/A'] == 'For') & (df_for['situation'] == "OpenPlay")]['X'].tolist())
            dist_for_y.append(df_for[(df_for['important_team'] == self.team) & (df_for['match_id'] == indices[i]) & (df_for['F/A'] == 'For') & (df_for['situation'] == "OpenPlay")]['Y'].tolist())
            dist_ag_x.append(df_ag[(df_ag['important_team'] == self.team) & (df_ag['match_id'] == indices[i]) & (df_ag['F/A'] == 'Against') & (df_ag['situation'] == "OpenPlay")]['X'].tolist())
            dist_ag_y.append(df_ag[(df_ag['important_team'] == self.team) & (df_ag['match_id'] == indices[i]) & (df_ag['F/A'] == 'Against') & (df_ag['situation'] == "OpenPlay")]['Y'].tolist())
        xG_diff = [xG_for_per_match[i]-xG_ag_per_match[i] for i in range(len(xG_for_per_match))]
        
        a1, a2 = 0, 0
        for i in range(len(big_chances_for)):
            a1 = a1 + len(big_chances_for[i])
        for i in range(len(big_chances_ag)):
            a2 = a2 + len(big_chances_ag[i])
        
        flat_dist_for_x = [elem for sublist in dist_for_x for elem in sublist]
        flat_dist_for_y = [elem for sublist in dist_for_y for elem in sublist]
        flat_dist_ag_x = [elem for sublist in dist_ag_x for elem in sublist]
        flat_dist_ag_y = [elem for sublist in dist_ag_y for elem in sublist]
        
        dist_for, dist_ag = [], []
        for i in range(len(dist_for_x)):
            dist_for.append(math.sqrt((122-flat_dist_for_x[i]*122)**2+(40-flat_dist_for_y[i]*40)**2))
        for i in range(len(dist_ag_x)):
            dist_ag.append(math.sqrt((122-flat_dist_ag_x[i]*122)**2+(40-flat_dist_ag_y[i]*40)**2))
        
        n_big_for, n_big_ag = a1/index, a2/index ## Big chances per game
        distance_for, distance_ag = sum(dist_for)/len(dist_for), sum(dist_ag)/len(dist_ag) ## Average shoting distance 
        return avg_xG_for, avg_xG_ag, xG_for_per_match, xG_ag_per_match, n_big_for, n_big_ag, distance_for, distance_ag
    
    def __plot_xG_fig(self,X1,X2):
        U, V = [], []
        for i in range(1,len(X1)):
            U.append(X1[i]-X1[i-1])
            V.append(X2[i]-X2[i-1])
        U.append(0)
        V.append(0)
        fig, ax = plt.subplots()
        
        ax.quiver(X1,X2,U,V,angles='xy',scale=1,scale_units='xy')
        ax.set_xlabel("average xG for per match")
        ax.set_ylabel("average xG against per match")
        ax.set_title(self.team)
        for i in range(len(self.seasons)):
            ax.annotate(self.seasons[i],(X1[i],X2[i]))
        plt.show()
    
    def __plot_histo(self,data_for,data_against,s):
        avg_val_for = sum(data_for)/len(data_for)
        avg_val_ag = sum(data_against)/len(data_against)
        
        fig, (ax1, ax2) = plt.subplots(1,2,figsize=(15,7.5))
        
        bins1 = [i for i in np.arange(0,5,0.4)]
        p1, _, _ = ax1.hist(data_for,bins=bins1,edgecolor='black')
        ax1.set_title(self.team + ": " + str(s))
        ax1.set_xlabel("Bins of xG created")
        ax1.set_ylabel("Number of matches")
        ax1.axvline(x=avg_val_for,linestyle='--',color='red')
        
        bins2 = [i for i in np.arange(0,5,0.4)]
        p2, _, _ = ax2.hist(data_against,bins=bins2,edgecolor='black')
        ax2.set_title(self.team + ": " + str(s))
        ax2.set_xlabel("Bins of xG conceded")
        ax2.set_ylabel("Number of matches")
        ax2.axvline(x=avg_val_ag,linestyle='--',color='red')
    
    def __attack_defense(self,big_for,big_ag,dist_for,dist_ag):
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2,2,figsize=(10,10))
        #fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2,2)
        fig.tight_layout(h_pad=12)

        ax1.plot(self.seasons,big_for)
        ax1.set_title("Attack")
        ax1.set_xticklabels(self.seasons,rotation=90)
        ax1.set_ylabel("average created big chances per match")
        
        ax2.plot(self.seasons,big_ag)
        ax2.set_title("Defence")
        ax2.set_xticklabels(self.seasons,rotation=90)
        ax2.set_ylabel("average conceded big chances per match")
        
        ax3.plot(self.seasons,dist_for)
        ax3.set_title("Attack")
        ax3.set_xticklabels(self.seasons,rotation=90)
        ax3.set_ylabel("Average shot distance")
        
        ax4.plot(self.seasons,dist_ag)
        ax4.set_title("Defence")
        ax4.set_xticklabels(self.seasons,rotation=90)
        ax4.set_ylabel("Average shot distance")
    
    def analyze_team(self):
        self.__check_seasons()
        xG_for, xG_ag, big_for, big_ag, dist_for, dist_ag = [], [], [], [], [], []
        for i in range(len(self.seasons)):
            f,a,data_for,data_ag, v1, v2, v3, v4 = self.__find_values(i)
            xG_for.append(f)
            xG_ag.append(a)
            big_for.append(v1)
            big_ag.append(v2)
            dist_for.append(v3)
            dist_ag.append(v4)
            self.__plot_histo(data_for,data_ag,self.seasons[i])
        self.__plot_xG_fig(xG_for,xG_ag)
        self.__attack_defense(big_for,big_ag,dist_for,dist_ag)

class CheckFile:
    def __init__(self):
        script_directory = os.path.dirname(os.path.abspath(__file__))
        if not os.path.exists(os.path.join(script_directory,"teams_dict.json")):
            exit("File 'teams_dict.json' does not exist.")
        with open(os.path.join(script_directory,"teams_dict.json")) as rf:
            self.data = json.load(rf)
        self.get_data()
    
    def get_data(self):
        return self.data

if __name__ == "__main__":
    pass