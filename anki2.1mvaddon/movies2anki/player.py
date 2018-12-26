# -*- coding: utf-8 -*-
#
# Original Source: https://github.com/dae/ankiplugins/blob/master/archive/customPlayer.py
# Original Source: "Refocus Card when Reviewing" add-on.
# Original Source: "Ignore space/enter when answer shown" add-on
# Original Source: https://github.com/ospalh/anki-addons/blob/develop/png_play_button.py
#

import subprocess, sys, time, re, atexit
import anki.sound as s

from anki.lang import _, ngettext
from anki.hooks import addHook, wrap
from aqt.reviewer import Reviewer
from aqt import mw, browser
from aqt.utils import showWarning, showInfo, tooltip, isWin, isMac
from aqt.qt import *
from PyQt4.QtGui import QIcon
from distutils.spawn import find_executable

# ------------- ADDITIONAL OPTIONS -------------
ADJUST_AUDIO_STEP = 0.25
ADJUST_AUDIO_REPLAY_TIME = 2.5
VLC_DIR = ""
IINA_DIR = "/Applications/IINA.app/Contents/MacOS/IINA"
# ----------------------------------------------

info = None
if isWin:
    info = subprocess.STARTUPINFO()
    info.wShowWindow = subprocess.SW_HIDE
    info.dwFlags = subprocess.STARTF_USESHOWWINDOW

p = None

mpv_executable = find_executable("mpv")
ffmpeg_executable = find_executable("ffmpeg")

def timeToSeconds(t):
    hours, minutes, seconds, milliseconds = t.split('.')
    return int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(milliseconds) * 0.001

def secondsToTime(seconds, sep="."):
    ms = (seconds * 1000) % 1000
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return "%d%s%02d%s%02d.%03d" % (h, sep, m, sep, s, ms)

def playVideoClip(path=None, state=None, shift=None, isEnd=True, isPrev=False, isNext=False):
    global p, _player

    fields = {}
    for item in list(mw.reviewer.card.note().items()):
        fields[item[0]] = item[1]

    if not path:
        if state != None:
            path = fields["Audio"]
        else:
            path = fields["Video"]
    elif path.endswith(".mp3"): # workaround to fix replay button (R) without refreshing webview.
        path = fields["Audio"]
    else:
        path = fields["Video"]

    if mw.reviewer.state == "question" and mw.reviewer.card.model()["name"] == "movies2anki - subs2srs (video)":
        path = fields["Video"]

    m = re.match(r"^.*?_(\d+\.\d\d\.\d\d\.\d+)-(\d+\.\d\d\.\d\d\.\d+).*$", path)

    if not m:
        return

    time_start, time_end = m.groups()
    time_start = timeToSeconds(time_start)
    time_end = timeToSeconds(time_end)

    if state == None and (isPrev or isNext):
        cards = sorted(mw.col.findCards("deck:current ", order=True))
        card_idx = cards.index(mw.reviewer.card.id)

        prev_card_idx = card_idx - 1 if card_idx - 1 > 0 else 0
        next_card_idx = card_idx + 1
        if next_card_idx >= len(cards):
            next_card_idx = len(cards) - 1

        if (isPrev and mw.col.getCard(cards[prev_card_idx]).id == mw.reviewer.card.id):
            tooltip("It's the first card.")
            return
        if (isNext and mw.col.getCard(cards[next_card_idx]).id == mw.reviewer.card.id):
            tooltip("It's the last card.")
            return

        curr_card = mw.col.getCard(cards[card_idx])
        prev_card = mw.col.getCard(cards[prev_card_idx])
        next_card = mw.col.getCard(cards[next_card_idx])

        prev_card_audio = prev_card.note()["Audio"]
        next_card_audio = next_card.note()["Audio"]

        # TODO compare Id field prefix or Source field or limit search by Source or maybe something else

        m = re.match(r"^.*?_(\d+\.\d\d\.\d\d\.\d+)-(\d+\.\d\d\.\d\d\.\d+).*$", prev_card_audio)

        prev_time_start, prev_time_end = m.groups()
        prev_time_start = timeToSeconds(prev_time_start)
        prev_time_end = timeToSeconds(prev_time_end)

        m = re.match(r"^.*?_(\d+\.\d\d\.\d\d\.\d+)-(\d+\.\d\d\.\d\d\.\d+).*$", next_card_audio)

        next_time_start, next_time_end = m.groups()
        next_time_start = timeToSeconds(next_time_start)
        next_time_end = timeToSeconds(next_time_end)

        if isPrev:
            time_start = prev_time_start

        if isNext:
            time_end = next_time_end

    if state != None:
        if state == "start":
            time_start = time_start - shift
        elif state == "end":
            time_end = time_end + shift
        elif state == "start reset":
            m = re.match(r"^.*?_(\d+\.\d\d\.\d\d\.\d+)-(\d+\.\d\d\.\d\d\.\d+).*$", fields["Id"])
            id_time_start, id_time_end = m.groups()
            id_time_start = timeToSeconds(id_time_start)
            time_start = id_time_start
        elif state == "end reset":
            m = re.match(r"^.*?_(\d+\.\d\d\.\d\d\.\d+)-(\d+\.\d\d\.\d\d\.\d+).*$", fields["Id"])
            id_time_start, id_time_end = m.groups()
            id_time_end = timeToSeconds(id_time_end)
            time_end = id_time_end

        time_interval = "%s-%s" % (secondsToTime(time_start), secondsToTime(time_end))
        mw.reviewer.card.note()["Audio"] = re.sub(r"_\d+\.\d\d\.\d\d\.\d+-\d+\.\d\d\.\d\d\.\d+\.", "_%s." % time_interval, fields["Audio"])
        mw.reviewer.card.note()["Video"] = re.sub(r"_\d+\.\d\d\.\d\d\.\d+-\d+\.\d\d\.\d\d\.\d+\.", "_%s." % time_interval, fields["Video"])
        mw.reviewer.card.note().flush()

    if VLC_DIR:
        args = ["-I", "dummy", "--dummy-quiet", "--play-and-exit", "--no-video-title"]
    else:
        args = ["--pause=no"]

    if state == None:
        if VLC_DIR:
            args += ["--start-time={}".format(time_start)]
            if isEnd:
                args += ["--stop-time={}".format(time_end)]
        else:
            args += ["--start={}".format(time_start)]
            if isEnd:
                args += ["--end={}".format(time_end)]
    elif state == "start" or state == "start reset":
        if VLC_DIR:
            args += ["--start-time={}".format(time_start), "--stop-time={}".format(time_end)]
        else:
            args += ["--start={}".format(time_start), "--end={}".format(time_end)]
    elif state == "end" or state == "end reset":
        if VLC_DIR:
            args += ["--start-time={}".format(time_end - ADJUST_AUDIO_REPLAY_TIME), "--stop-time={}".format(time_end)]
        else:
            args += ["--start={}".format(time_end - ADJUST_AUDIO_REPLAY_TIME), "--end={}".format(time_end)]

    if (path.endswith(".mp3") and not isPrev and not isNext) or state != None:
        if VLC_DIR:
            args += ["--no-video"]
        else:
            args += ["--force-window=no", "--video=no"]
            args += ["--af=afade=t=in:st=%s:d=%s,afade=t=out:st=%s:d=%s" % (time_start, 0.25, time_end - 0.25, 0.25)]
    else:
        if VLC_DIR:
            args += ["--no-sub-autodetect-file"]
        else:
            args += ["--sub-visibility=no"]
            if not (state == None and isEnd == False):
                args += ["--af=afade=t=out:st=%s:d=%s" % (time_end - 0.25, 0.25)]

    fullpath = fields["Path"].encode(sys.getfilesystemencoding())

    if VLC_DIR:
        cmd = [VLC_DIR] + args + [os.path.normpath(fullpath)]
    else:
        if isMac and os.path.exists(IINA_DIR):
            args = [o.replace("--", "--mpv-") for o in args]
            cmd = [IINA_DIR] + args + [fullpath]
        else:
            cmd = [mpv_executable] + args + [fullpath]

    if p != None and p.poll() is None:
        p.kill()

    p = subprocess.Popen(cmd, startupinfo = info)

def queueExternal(path):
    global p, _player

    if mw.state == "review" and mw.reviewer.card != None and (mw.reviewer.card.model()["name"] == "movies2anki (add-on)" or mw.reviewer.card.model()["name"].startswith("movies2anki - subs2srs")):
        if mw.reviewer.state == "answer" and path.endswith(".mp4"):
            return

        try:
            clearExternalQueue()
            playVideoClip(path)
        except OSError:
            return showWarning(r"""<p>Please install <a href='https://mpv.io'>mpv</a>.</p>
                On Windows download mpv and either update PATH environment variable or put mpv.exe in Anki installation folder (C:\Program Files\Anki).""", parent=mw)
    else:
        _player(path)

def _stopPlayer():
    global p
    
    if p != None and p.poll() is None:
        p.kill()

addHook("unloadProfile", _stopPlayer)
atexit.register(_stopPlayer)

def clearExternalQueue():
    global _queueEraser
    
    _stopPlayer()
    _queueEraser()

_player = s._player
s._player = queueExternal

_queueEraser = s._queueEraser
s._queueEraser = clearExternalQueue

def adjustAudio(state, shift=None):
    if mw.state == "review" and mw.reviewer.card != None and (mw.reviewer.card.model()["name"] == "movies2anki (add-on)" or mw.reviewer.card.model()["name"].startswith("movies2anki - subs2srs")):
        try:
            clearExternalQueue()
            playVideoClip(state=state, shift=shift)
        except OSError:
            return showWarning(r"""<p>Please install <a href='https://mpv.io'>mpv</a>.</p>
                On Windows download mpv and either update PATH environment variable or put mpv.exe in Anki installation folder (C:\Program Files\Anki).""", parent=mw)

def selectVideoPlayer():
    global VLC_DIR
    try:
        if isMac and os.path.exists(IINA_DIR):
            return

        p = subprocess.Popen([mpv_executable, "--version"], startupinfo = info)
        if p != None and p.poll() is None:
            p.kill()
    except OSError:
        if VLC_DIR != "" and os.path.exists(VLC_DIR):
            return
        
        VLC_DIR = r"C:\Program Files\VideoLAN\VLC\vlc.exe"
        if os.path.exists(VLC_DIR):
            return

        VLC_DIR = r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe"
        if os.path.exists(VLC_DIR):
            return

        return showWarning(r"""<p>Neither mpv nor VLC were found.</p>
            <p>Please install <a href='https://mpv.io'>mpv</a>.</p>
            On Windows download mpv and either update PATH environment variable or put mpv.exe in Anki installation folder (C:\Program Files\Anki).""", parent=mw)

addHook("profileLoaded", selectVideoPlayer)

def _newKeyHandler(self, evt, _old):
    key = str(evt.text())

    if self.card.model()["name"] == "movies2anki (add-on)" or self.card.model()["name"].startswith("movies2anki - subs2srs"):
        if key == "," and evt.modifiers() == Qt.NoModifier:
            adjustAudio("start", ADJUST_AUDIO_STEP)
        elif key == "." and evt.modifiers() == Qt.NoModifier:
            adjustAudio("start", -1.0 * ADJUST_AUDIO_STEP)
        elif key == "<": # Shift+,
            adjustAudio("end", -1.0 * ADJUST_AUDIO_STEP)
        elif key == ">": # Shift+.
            adjustAudio("end", ADJUST_AUDIO_STEP)
        elif key == "," and evt.modifiers() == (Qt.ControlModifier | Qt.ShiftModifier):
            adjustAudio("start reset")
        elif key == "." and evt.modifiers() == (Qt.ControlModifier | Qt.ShiftModifier):
            adjustAudio("end reset")

    return _old(self, evt)

def replayVideo(isEnd=True, isPrev=False, isNext=False):
    if mw.state == "review" and mw.reviewer.card != None and (mw.reviewer.card.model()["name"] == "movies2anki (add-on)" or mw.reviewer.card.model()["name"].startswith("movies2anki - subs2srs")):
        clearExternalQueue()
        playVideoClip(isEnd=isEnd, isPrev=isPrev, isNext=isNext)

def joinCard(isPrev=False, isNext=False):
    if mw.state == "review" and mw.reviewer.card != None and (mw.reviewer.card.model()["name"] == "movies2anki (add-on)" or mw.reviewer.card.model()["name"].startswith("movies2anki - subs2srs")):
        m = re.match(r"^(.*?)_(\d+\.\d\d\.\d\d\.\d+)-(\d+\.\d\d\.\d\d\.\d+).*$", mw.reviewer.card.note()["Audio"])

        card_prefix, time_start, time_end = m.groups()
        time_start = timeToSeconds(time_start)
        time_end = timeToSeconds(time_end)

        cards = sorted(mw.col.findCards("deck:current ", order=True))
        card_idx = cards.index(mw.reviewer.card.id)

        prev_card_idx = card_idx - 1 if card_idx - 1 > 0 else 0
        next_card_idx = card_idx + 1
        if next_card_idx >= len(cards):
            next_card_idx = len(cards) - 1

        if (isPrev and mw.col.getCard(cards[prev_card_idx]).id == mw.reviewer.card.id) or \
            (isNext and mw.col.getCard(cards[next_card_idx]).id == mw.reviewer.card.id):
            tooltip("Nothing to do.")
            return

        curr_card = mw.col.getCard(cards[card_idx]).note()
        prev_card = mw.col.getCard(cards[prev_card_idx]).note()
        next_card = mw.col.getCard(cards[next_card_idx]).note()

        if (isPrev and prev_card["Source"] != curr_card["Source"]) or (isNext and curr_card["Source"] != next_card["Source"]):
           showInfo("Cards can't be joined due to the Source field difference.")
           return

        curr_card_audio = curr_card["Audio"]
        prev_card_audio = prev_card["Audio"]
        next_card_audio = next_card["Audio"]

        m = re.match(r"^.*?_(\d+\.\d\d\.\d\d\.\d+)-(\d+\.\d\d\.\d\d\.\d+).*$", curr_card_audio)

        curr_time_start, curr_time_end = m.groups()
        curr_time_start = timeToSeconds(curr_time_start)
        curr_time_end = timeToSeconds(curr_time_end)

        m = re.match(r"^.*?_(\d+\.\d\d\.\d\d\.\d+)-(\d+\.\d\d\.\d\d\.\d+).*$", prev_card_audio)

        prev_time_start, prev_time_end = m.groups()
        prev_time_start = timeToSeconds(prev_time_start)
        prev_time_end = timeToSeconds(prev_time_end)

        m = re.match(r"^.*?_(\d+\.\d\d\.\d\d\.\d+)-(\d+\.\d\d\.\d\d\.\d+).*$", next_card_audio)

        next_time_start, next_time_end = m.groups()
        next_time_start = timeToSeconds(next_time_start)
        next_time_end = timeToSeconds(next_time_end)

        if isPrev:
            time_start = prev_time_start

        if isNext:
            time_end = next_time_end

        c = mw.reviewer.card.note()
        for name, val in list(c.items()):
            if name == "Id":
                c[name] = "%s_%s-%s" % (card_prefix, secondsToTime(time_start), secondsToTime(time_end))
            elif name == "Audio":
                c[name] = "%s_%s-%s.mp3" % (card_prefix, secondsToTime(time_start), secondsToTime(time_end))
            elif name == "Video":
                c[name] = "%s_%s-%s.mp4" % (card_prefix, secondsToTime(time_start), secondsToTime(time_end))
            elif name == "Source":
                pass
            elif name == "Path":
                pass
            elif name == "Audio Sound":
                c["Audio Sound"] = ""
            elif name == "Video Sound":
                c["Video Sound"] = ""
            else:
                if isPrev:
                    c[name] = prev_card[name] + "<br>" + c[name]
                else:
                    c[name] = c[name] + "<br>" + next_card[name]

        mw.checkpoint(_("Delete"))

        c.flush()

        if isPrev:
            cd = prev_card
        else:
            cd = next_card

        cnt = len(cd.cards())
        mw.col.remNotes([cd.id])
        mw.reset()

        tooltip(ngettext(
            "Note joined and its %d card deleted.",
            "Note joined and its %d cards deleted.",
            cnt) % cnt)

def addReplayVideoShortcut():
    mw.replayVideoShortcut = QShortcut(QKeySequence("Ctrl+R"), mw)
    mw.connect(mw.replayVideoShortcut, SIGNAL("activated()"), replayVideo)
    
    mw.replayVideoWithoutEndShortcut = QShortcut(QKeySequence("Shift+R"), mw)
    mw.connect(mw.replayVideoWithoutEndShortcut, SIGNAL("activated()"), lambda: replayVideo(isEnd=False))

    mw.replayPrevVideoShortcut = QShortcut(QKeySequence("["), mw)
    mw.connect(mw.replayPrevVideoShortcut, SIGNAL("activated()"), lambda: replayVideo(isPrev=True))

    mw.replayNextVideoShortcut = QShortcut(QKeySequence("]"), mw)
    mw.connect(mw.replayNextVideoShortcut, SIGNAL("activated()"), lambda: replayVideo(isNext=True))

    mw.joinPrevCardShortcut = QShortcut(QKeySequence("Shift+["), mw)
    mw.connect(mw.joinPrevCardShortcut, SIGNAL("activated()"), lambda: joinCard(isPrev=True))

    mw.joinNextCardShortcut = QShortcut(QKeySequence("Shift+]"), mw)
    mw.connect(mw.joinNextCardShortcut, SIGNAL("activated()"), lambda: joinCard(isNext=True))

addHook("profileLoaded", addReplayVideoShortcut)

Reviewer._keyHandler = wrap(Reviewer._keyHandler, _newKeyHandler, "around")

class MediaWorker(QThread):
    updateProgress = pyqtSignal(int)
    updateProgressText = pyqtSignal(str)
    updateNote = pyqtSignal(str, str, str)
    jobFinished = pyqtSignal(float)

    def __init__(self, data):
        QThread.__init__(self)

        self.data = data
        self.canceled = False
        self.fp = None

    def cancel(self):
        self.canceled = True

        if self.fp != None:
            self.fp.terminate()

    def run(self):
        job_start = time.time()
        for idx, note in enumerate(self.data):
            if self.canceled:
                break

            self.updateProgress.emit((idx * 1.0 / len(self.data)) * 100)

            fld = note["Audio"]

            time_start, time_end = re.match(r"^.*?_(\d+\.\d\d\.\d\d\.\d+)-(\d+\.\d\d\.\d\d\.\d+).*$", fld).groups()

            ss = secondsToTime(timeToSeconds(time_start), sep=":")
            t = timeToSeconds(time_end) - timeToSeconds(time_start)

            af_d = 0.25
            af_st = 0
            af_to = t - af_d
            af_params = "afade=t=in:st=%s:d=%s,afade=t=out:st=%s:d=%s" % (af_st, af_d, af_to, af_d)

            # TODO select the last stream by default
            audio_id = 0

            # TODO
            vf = "scale=480:-2"

            self.updateProgressText.emit(note["Source"] + "  " + ss)

            if note["Audio Sound"] == "" or not os.path.exists(note["Audio"]):
                self.fp = None
                cmd = " ".join([ffmpeg_executable, "-y", "-ss", ss, "-i", '"' + note["Path"] + '"', "-loglevel", "quiet", "-t", str(t), "-af", af_params, "-map", "0:a:" + str(audio_id), '"' + note["Audio"] + '"'])
                self.fp = subprocess.Popen(cmd.encode(sys.getfilesystemencoding()), shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, startupinfo = info)
                self.fp.wait()

                if self.canceled:
                    break

                self.updateNote.emit(str(note.id), "Audio Sound", note["Audio"])

            if "Video Sound" in note and (note["Video Sound"] == "" or not os.path.exists(note["Video"])):
                self.fp = None
                cmd = " ".join([ffmpeg_executable, "-y", "-ss", ss, "-i", '"' + note["Path"] + '"', "-strict", "-2", "-loglevel", "quiet", "-t", str(t), "-af", af_params, "-map", "0:v:0", "-map", "0:a:" + str(audio_id), "-c:v", "libx264", "-vf", vf, "-profile:v", "baseline", "-level", "3.0", "-c:a", "aac", "-ac", "2", '"' + note["Video"] + '"'])
                self.fp = subprocess.Popen(cmd.encode(sys.getfilesystemencoding()), shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, startupinfo = info)
                self.fp.wait()

                if self.canceled:
                    break

                self.updateNote.emit(str(note.id), "Video Sound", note["Video"])

        job_end = time.time()
        time_diff = (job_end - job_start)

        if not self.canceled:
            self.updateProgress.emit(100)
            self.jobFinished.emit(time_diff)

def cancelProgressDialog():
    mw.worker.cancel()

def setProgress(progress):
    mw.progressDialog.setValue(progress)

def setProgressText(text):
    mw.progressDialog.setLabelText(text)

def saveNote(nid, fld, val):
    note = mw.col.getNote(nid)
    note[fld] = "[sound:%s]" % val
    note.flush()

def finishProgressDialog(time_diff):
    mw.progressDialog.done(0)
    minutes = int(time_diff / 60)
    seconds = int(time_diff % 60)
    message = "Processing completed in %s minutes %s seconds." % (minutes, seconds)
    QMessageBox.information(mw, "movies2anki", message)

def update_media():
    global ffmpeg_executable

    if not ffmpeg_executable:
        ffmpeg_executable = find_executable("ffmpeg")

    if not ffmpeg_executable:
        return showWarning(r"""<p>Please install <a href='https://www.ffmpeg.org'>FFmpeg</a>.</p>
        On Windows download FFmpeg and either update PATH environment variable or put ffmpeg.exe in Anki installation folder (C:\Program Files\Anki).""", parent=mw)

    if hasattr(mw, 'worker') and mw.worker != None and mw.worker.isRunning():
        mw.progressDialog.setWindowState(mw.progressDialog.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)
        mw.progressDialog.activateWindow()
        return
    
    data = []
    for model_name in ["movies2anki (add-on)", "movies2anki - subs2srs", "movies2anki - subs2srs (video)"]:
        m = mw.col.models.byName(model_name)

        if m == None:
            continue

        mid = m['id']
        query = "mid:'%s'" % (mid)
        res = mw.col.findNotes(query)

        if len(res) == 0:
            continue

        if "Audio Sound" not in mw.col.models.fieldNames(m) or ("Video Sound" not in mw.col.models.fieldNames(m) and m["name"] == "movies2anki (add-on)"):
            mw.progress.start()

            if "Audio Sound" not in mw.col.models.fieldNames(m):
                fm = mw.col.models.newField("Audio Sound")
                mw.col.models.addField(m, fm)
                mw.col.models.save(m)

            if "Video Sound" not in mw.col.models.fieldNames(m) and m["name"] == "movies2anki (add-on)":
                fm = mw.col.models.newField("Video Sound")
                mw.col.models.addField(m, fm)
                mw.col.models.save(m)

            mw.progress.finish()
            mw.reset()

        nids = sorted(res)
        for nid in nids:
            note = mw.col.getNote(nid)

            if note["Audio Sound"] == "" or not os.path.exists(note["Audio"]):
                data.append(note)
            elif m["name"] == "movies2anki (add-on)" and (note["Video Sound"] == "" or not os.path.exists(note["Video"])):
                data.append(note)

    if len(data) == 0:
        tooltip("Nothing to update")
        return

    if hasattr(mw, 'progressDialog'):
        del mw.progressDialog

    mw.progressDialog = QProgressDialog()
    mw.progressDialog.setWindowIcon(QIcon(":/icons/anki.png"))
    mw.progressDialog.setWindowTitle("Generating Media")
    flags = mw.progressDialog.windowFlags()
    flags ^= Qt.WindowMinimizeButtonHint
    mw.progressDialog.setWindowFlags(flags)
    mw.progressDialog.setFixedSize(300, mw.progressDialog.height())
    mw.progressDialog.setCancelButtonText("Cancel")
    mw.progressDialog.setMinimumDuration(0)
    mw.progress_bar = QProgressBar(mw.progressDialog)
    mw.progress_bar.setAlignment(Qt.AlignCenter)
    mw.progressDialog.setBar(mw.progress_bar)

    mw.worker = MediaWorker(data)
    mw.worker.updateProgress.connect(setProgress)
    mw.worker.updateProgressText.connect(setProgressText)
    mw.worker.updateNote.connect(saveNote)
    mw.worker.jobFinished.connect(finishProgressDialog)
    mw.progressDialog.canceled.connect(cancelProgressDialog)
    mw.worker.start()

def stopWorker():
    if hasattr(mw, 'worker') and mw.worker != None:
        mw.worker.cancel()

addHook("unloadProfile", stopWorker)

update_media_action = QAction("Generate Mobile Cards...", mw)
update_media_action.triggered.connect(update_media)
mw.form.menuTools.addAction(update_media_action)