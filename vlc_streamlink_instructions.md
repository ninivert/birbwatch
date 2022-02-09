1. Install VLC
2. Open VLC, go into Advanced Settings, set "Demuxer module" to "Avcformat demuxer"
3. `conda create -n streamlink python=3.9`
4. `conda activate streamlink`
5. `which python && which pip  # confirm conda environment`
6. `conda activate streamlink`
7. `streamlink -p vlc --loglevel debug --verbose https://youtu.be/MMbTUvSjnB4 worst`
8. VLC should open

Start without VLC : `streamlink --loglevel debug --player-external-http https://youtu.be/MMbTUvSjnB4 worst`, then open the http stream in VLC

Other cams :
- https://live.hdontap.com/hls/hosb3/fobwr_eagles-ptz.stream/playlist.m3u8
- https://www.friendsofblackwater.org/camhtm2.html