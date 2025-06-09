let mediaRecorder = null;
let recordedChunks = [];

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'mute') {
    const videos = document.querySelectorAll('video');
    if (videos.length === 0) {
      sendResponse({ success: false, error: '未找到视频元素' });
      return;
    }
    videos.forEach(video => {
      video.muted = true;
    });

    const shadowHosts = document.querySelectorAll('*');
    shadowHosts.forEach(host => {
      if (host.shadowRoot) {
        const shadowVideos = host.shadowRoot.querySelectorAll('video');
        shadowVideos.forEach(video => {
          video.muted = true;
        });
      }
    });
    sendResponse({ success: true });
  } else if (request.action === 'unmute') {
    const videos = document.querySelectorAll('video');
    if (videos.length === 0) {
      sendResponse({ success: false, error: '未找到视频元素' });
      return;
    }
    videos.forEach(video => {
      video.muted = false;
    });

    const shadowHosts = document.querySelectorAll('*');
    shadowHosts.forEach(host => {
      if (host.shadowRoot) {
        const shadowVideos = host.shadowRoot.querySelectorAll('video');
        shadowVideos.forEach(video => {
          video.muted = false;
        });
      }
    });
    sendResponse({ success: true });
  } else if (request.action === 'startRecording') {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
      sendResponse({ success: false, error: '已在录制中' });
      return;
    }

    navigator.mediaDevices.getUserMedia({
      video: {
        mandatory: {
          chromeMediaSource: 'desktop',
          chromeMediaSourceId: request.streamId
        }
      },
      audio: {
        mandatory: {
          chromeMediaSource: 'desktop',
          chromeMediaSourceId: request.streamId
        }
      }
    }).then((stream) => {
      mediaRecorder = new MediaRecorder(stream, { mimeType: 'video/webm;codecs=vp8,opus' });
      recordedChunks = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          recordedChunks.push(event.data);
        }
      };

      mediaRecorder.onstop = () => {
        const blob = new Blob(recordedChunks, { type: 'video/webm' });
        const url = URL.createObjectURL(blob);
        chrome.runtime.sendMessage({ action: 'saveRecording', url: url });
        stream.getTracks().forEach(track => track.stop());
        mediaRecorder = null;
        recordedChunks = [];
      };

      mediaRecorder.onerror = (event) => {
        console.error('MediaRecorder error:', event.error);
        chrome.runtime.sendMessage({ action: 'recordingError', error: event.error.message });
      };

      mediaRecorder.start(1000); // Split into 1-second chunks to reduce memory pressure
      sendResponse({ success: true });
    }).catch((error) => {
      console.error('getUserMedia error:', error);
      sendResponse({ success: false, error: error.message });
    });
    return true; // Keep message channel open for async response
  } else if (request.action === 'stopRecording') {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
      mediaRecorder.stop();
      sendResponse({ success: true });
    } else {
      sendResponse({ success: false, error: '未在录制中' });
    }
  }
});