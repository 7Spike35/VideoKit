chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'startRecording') {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (!tabs[0]) {
        sendResponse({ success: false, error: '无法找到活动标签页' });
        return;
      }

      const tab = tabs[0];
      if (!tab.url || tab.url.startsWith('chrome://') || tab.url.startsWith('edge://')) {
        sendResponse({ success: false, error: '无法在当前标签页录屏' });
        return;
      }

      chrome.desktopCapture.chooseDesktopMedia(['screen', 'window'], tab, (streamId) => {
        if (!streamId) {
          sendResponse({ success: false, error: '用户取消选择' });
          return;
        }

        chrome.tabs.sendMessage(tab.id, { action: 'startRecording', streamId: streamId }, (response) => {
          if (chrome.runtime.lastError) {
            sendResponse({ success: false, error: chrome.runtime.lastError.message });
          } else {
            sendResponse(response);
          }
        });
      });
    });
    return true;
  } else if (request.action === 'stopRecording') {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (!tabs[0]) {
        sendResponse({ success: false, error: '无法找到活动标签页' });
        return;
      }

      chrome.tabs.sendMessage(tabs[0].id, { action: 'stopRecording' }, (response) => {
        if (chrome.runtime.lastError) {
          sendResponse({ success: false, error: chrome.runtime.lastError.message });
        } else {
          sendResponse(response);
        }
      });
    });
    return true;
  } else if (request.action === 'saveRecording') {
    chrome.downloads.download({
      url: request.url,
      filename: `screen_recording_${Date.now()}.webm`
    }, () => {
      URL.revokeObjectURL(request.url);
    });
    sendResponse({ success: true });
    return true;
  } else if (request.action === 'recordingError') {
    sendResponse({ success: false, error: request.error });
    return true;
  }
});