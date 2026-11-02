// Voice input (English): browser Web Speech API (en-IN) first; falls back to recording audio and
// sending it to the backend's open-source Whisper (faster-whisper) endpoint.
import { useRef, useState } from "react";
import { api } from "../../api/client";

export function useSpeech(onText: (text: string, final: boolean) => void) {
  const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
  const [listening, setListening] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const rec = useRef<any>(null);
  const media = useRef<MediaRecorder | null>(null);

  const start = async () => {
    setError(null);
    if (SR) {
      const r = new SR();
      r.lang = "en-IN"; r.interimResults = true; r.continuous = false; r.maxAlternatives = 1;
      r.onresult = (e: any) => {
        let text = "";
        for (let i = 0; i < e.results.length; i++) text += e.results[i][0].transcript;
        onText(text, e.results[e.results.length - 1].isFinal);
      };
      r.onerror = (e: any) => { setError(e.error === "not-allowed" ? "Microphone permission denied" : `Speech error: ${e.error}`); setListening(false); };
      r.onend = () => setListening(false);
      rec.current = r; r.start(); setListening(true);
      return;
    }
    try {   // fallback: record and transcribe on the server
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mr = new MediaRecorder(stream); const chunks: Blob[] = [];
      mr.ondataavailable = e => chunks.push(e.data);
      mr.onstop = async () => {
        stream.getTracks().forEach(t => t.stop()); setListening(false);
        const fd = new FormData(); fd.append("audio", new Blob(chunks, { type: "audio/webm" }), "query.webm");
        try { const r = await api.upload<{ text: string }>("/api/voice/transcribe", fd); onText(r.text, true); }
        catch (e: any) { setError(e.message); }
      };
      media.current = mr; mr.start(); setListening(true);
      setTimeout(() => mr.state === "recording" && mr.stop(), 8000);
    } catch { setError("Microphone not available in this browser"); }
  };
  const stop = () => { rec.current?.stop(); if (media.current?.state === "recording") media.current.stop(); setListening(false); };
  return { listening, start, stop, error, browserSTT: !!SR };
}
