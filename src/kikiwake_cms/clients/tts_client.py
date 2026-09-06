import random
from dataclasses import dataclass

import google.cloud.texttospeech as tts
from google.cloud.texttospeech import Voice

from ..config import Settings


@dataclass
class TtsOutput:
    bytes: bytes
    language: str
    country: str
    text: str
    gender: int
    name: str


class TtsClient:
    def __init__(self, settings: Settings):
        self._client = tts.TextToSpeechClient(transport="rest")
        voices_response = self._client.list_voices(language_code="en-US")
        self.voices = [
            voice
            for voice in voices_response.voices
            if settings.tts_voice_filter in voice.name
        ]

    def _random_voice(self) -> Voice:
        index = random.randint(0, len(self.voices) - 1)
        return self.voices[index]

    def synthesize(self, text: str) -> TtsOutput:
        synthesis_input = tts.SynthesisInput(text=text)
        voice = self._random_voice()
        language_code = (
            "en-US" if len(voice.language_codes) == 0 else voice.language_codes[0]
        )
        language, country = language_code.lower().split("-")
        voice_param = tts.VoiceSelectionParams(
            language_code=language_code,
            name=voice.name,
            ssml_gender=voice.ssml_gender,
        )
        audio_config = tts.AudioConfig(audio_encoding=tts.AudioEncoding.MP3)
        response = self._client.synthesize_speech(
            input=synthesis_input,
            voice=voice_param,
            audio_config=audio_config,
        )

        return TtsOutput(
            bytes=response.audio_content,
            language=language,
            country=country,
            text=text,
            gender=voice.ssml_gender.value,
            name=voice.name,
        )
