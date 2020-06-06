#!/usr/bin/python3

import os
from pathlib import PurePath
# import json
import spotipy
import argparse

class SpotifyUpsync:
    def __init__(self, input_path):
        self.USER = 'tylrr_nt'
        self.SCOPE = 'playlist-modify-public'
        self.input_path = input_path
        # ensure environment variables are set to proceed
        token = spotipy.util.prompt_for_user_token(self.USER, scope=self.SCOPE)
        if token:
            self.sp = spotipy.Spotify(auth=token)
            self.sp_playlists_results = self.sp.user_playlists(self.USER)
            self.sp_playlists_names = [item['name'] for item in self.sp_playlists_results['items']]
            self.sp_playlists_ids = [item['id'] for item in self.sp_playlists_results['items']]

    def spotify_upsync(self):
        if os.path.isdir(self.input_path):
            for dir_name, subdir_list, file_list in os.walk(self.input_path):
                for playlist in file_list:
                    self.playlist_sync(dir_name, playlist, file_list)
        elif os.path.isfile(self.input_path):
            self.playlist_sync('.', playlist, file_list)
                        
    def playlist_sync(self, dir_name, playlist, file_list):
        playlist = PurePath(dir_name, playlist)

        if playlist.suffix == '.m3u':
            print('Current playlist: ' + playlist.stem)

            local_playlist_data = open(playlist, errors='ignore')
            lines = local_playlist_data.readlines()
            local_playlist_data.close()

            if playlist.stem not in self.sp_playlists_names:
                print('A new playlist will be created in Spotify!')
                local_track_names = [PurePath(line.replace('\\', '/')).stem for line in lines]
                local_track_ids = self.query_track(local_track_names)
                
                np = self.sp.user_playlist_create(self.USER, playlist.stem)
                playlist_id = np['id']

                # we may be length limited
                for track_pack in self.pack_add_tracks(local_track_ids):
                    self.sp.user_playlist_add_tracks(self.USER, playlist_id, track_pack)

            else:
                print(playlist.stem + ' will be modified in Spotify!')
                local_mod_time = os.path.getmtime(playlist)
                local_track_names = [PurePath(line.replace('\\', '/')).stem for line in lines]
                local_track_ids = self.query_track(local_track_names)

                playlist_id = self.sp_playlists_ids[self.sp_playlists_names.index(playlist.stem)]
                sp_playlist_tracks_results = self.sp.playlist_tracks(playlist_id)
                sp_track_ids = [item['track']['id'] for item in sp_playlist_tracks_results['items']]

                while sp_playlist_tracks_results['next']:
                    sp_playlist_tracks_results = self.sp._get(sp_playlist_tracks_results['next'])
                    sp_track_ids += [item['track']['id'] for item in sp_playlist_tracks_results['items']]

                remove_tracks, add_tracks, remove_specific_tracks = self.align_tracks(local_track_ids, sp_track_ids)

                if remove_tracks:
                    self.sp.user_playlist_remove_all_occurrences_of_tracks(self.USER, playlist_id, remove_tracks)
                if add_tracks:
                    for track in add_tracks:
                        self.sp.user_playlist_add_tracks(self.USER, playlist_id, [track], add_tracks[track])
                if remove_specific_tracks:
                    self.sp.user_playlist_remove_specific_occurrences_of_tracks(self.USER, playlist_id, remove_specific_tracks)

    def pack_add_tracks(self, local_track_ids):
        bulk_tracks = list()

        for idx_track_id in range(0, len(local_track_ids), 100):
            if len(local_track_ids) - idx_track_id < 100:
                bulk_tracks.append(local_track_ids[idx_track_id:idx_track_id + (len(local_track_ids) - idx_track_id)])
            else:
                bulk_tracks.append(local_track_ids[idx_track_id:idx_track_id + 100])
        
        return bulk_tracks

    def align_tracks(self, local_track_ids, sp_track_ids):
        remove_tracks = set()
        add_tracks = {}

        # order matters -- first, scrub playlist of any tracks that don't belong
        # this does not take care of out-of-order tracks, which is why we need 3 loops
        for track_id in sp_track_ids:
            if track_id not in local_track_ids:
                remove_tracks.add(track_id)
                sp_track_ids.remove(track_id)
        
        # next, update the playlist with new tracks
        for index, track_id in enumerate(local_track_ids):
            if sp_track_ids[index] != track_id:
                add_tracks[track_id] = index
                sp_track_ids.insert(index, track_id)

        # finally, all of the out-of-order tracks will be pushed to the bottom, so remove these
        remove_specific_tracks = [{'uri': track_id, 'positions': [position]} for position, track_id in enumerate(sp_track_ids) if position >= len(local_track_ids)]

        return remove_tracks, add_tracks, remove_specific_tracks

    def query_track(self, lines):
        tracks = []
        for line in lines:
            search_results = self.sp.search(line.replace(' ', '+'))
            if search_results['tracks']['items']:
                # gets id of first track
                # print(search_results['tracks']['items'][0]['id'])
                tracks.append(search_results['tracks']['items'][0]['id'])
        
        return tracks

    def is_modified(self, playlist):
        
        return playlist

if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog='upsync', description='sync offline playlists to Spotify')

    parser.add_argument('input')

    args = parser.parse_args()

    syncer = SpotifyUpsync(args.input)
    syncer.spotify_upsync()