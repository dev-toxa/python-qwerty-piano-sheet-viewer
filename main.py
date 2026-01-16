import mido
import pygame
import sys
import os
import tkinter as tk
from tkinter import filedialog
import json

# --- 유튜브 쇼츠(Shorts) 및 사운드 설정 ---
WIDTH, HEIGHT = 540, 960  # 9:16 비율
FPS = 60
WHITE = (255, 255, 255)
BLACK = (30, 41, 59)
RED = (239, 68, 68)
ORANGE = (255, 60, 0)
YELLOW = (245, 158, 11)
BLUE = (37, 99, 235)
GRAY = (248, 250, 252)

# 설정 파일 경로
CONFIG_FILE = "midi_player_config.json"

# 동시 노트 판단 임계값
GROUPING_THRESHOLD_TICKS = 20

# MIDI 계명 이름
PITCH_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Keymapping
KEY_MAP = {
    "C1": "1", "C#1": "!", "D1": "2", "D#1": "@", "E1": "3", "F1": "4", "F#1": "$", "G1": "5", "G#1": "%", "A1": "6", "A#1": "^", "B1": "7",
    "C2": "8", "C#2": "*", "D2": "9", "D#2": "(", "E2": "0", "F2": "q", "F#2": "Q", "G2": "w", "G#2": "W", "A2": "e", "A#2": "E", "B2": "r",
    "C3": "t", "C#3": "T", "D3": "y", "D#3": "Y", "E3": "u", "F3": "i", "F#3": "I", "G3": "o", "G#3": "O", "A3": "p", "A#3": "P", "B3": "a",
    "C4": "s", "C#4": "S", "D4": "d", "D#4": "D", "E4": "f", "F4": "g", "F#4": "G", "G4": "h", "G#4": "H", "A4": "j", "A#4": "J", "B4": "k",
    "C5": "l", "C#5": "L", "D5": "z", "D#5": "Z", "E5": "x", "F5": "c", "F#5": "C", "G5": "v", "G#5": "V", "A5": "b", "A#5": "B", "B5": "n",
    "C6": "m", "C#6": "M"
}

class MIDIPlayer:
    def __init__(self, midi_path):
        pygame.init()
        try:
            pygame.mixer.pre_init(44100, -16, 2, 1024)
            pygame.mixer.init()
        except:
            print("Audio device not found.")
            
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("MIDI Shorts Player - 2 Measures Mode")
        self.clock = pygame.time.Clock()
        
        self.font = pygame.font.SysFont("Arial", 32, bold=True)
        self.small_font = pygame.font.SysFont("Arial", 20, bold=True)
        self.title_font = pygame.font.SysFont("Arial", 24, bold=True)
        
        self.midi_path = midi_path
        self.audio_latency_ms = self.load_config()
        
        self.is_playing = False
        self.current_ticks = 0.0 
        self.load_midi()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)
                    return data.get("audio_latency_ms", 160)
            except:
                return 160
        return 160

    def save_config(self):
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump({"audio_latency_ms": self.audio_latency_ms}, f)
        except Exception as e:
            print(f"Failed to save config: {e}")

    def get_key_char(self, midi_number):
        name = PITCH_NAMES[midi_number % 12]
        octave = (midi_number // 12) - 1
        note_key = f"{name}{octave}"
        return KEY_MAP.get(note_key, "?")

    def load_midi(self):
        try:
            self.mid = mido.MidiFile(self.midi_path)
            pygame.mixer.music.load(self.midi_path)
            pygame.mixer.music.set_volume(0.8) 
        except Exception as e:
            print(f"Error loading MIDI: {e}")
            sys.exit()

        self.ticks_per_beat = self.mid.ticks_per_beat
        self.ticks_per_measure = self.ticks_per_beat * 4
        
        raw_notes = []
        for track in self.mid.tracks:
            temp_tick = 0
            for msg in track:
                temp_tick += msg.time
                if msg.type == 'note_on' and msg.velocity > 0:
                    raw_notes.append({
                        'ticks': temp_tick,
                        'note': msg.note,
                        'char': self.get_key_char(msg.note)
                    })
        
        raw_notes.sort(key=lambda x: x['ticks'])
        
        self.measures = []
        if not raw_notes: return

        max_ticks = max(n['ticks'] for n in raw_notes)
        num_measures = (max_ticks // self.ticks_per_measure) + 1
        
        for i in range(num_measures):
            m_start = i * self.ticks_per_measure
            m_end = (i + 1) * self.ticks_per_measure
            m_notes = [n for n in raw_notes if m_start <= n['ticks'] < m_end]
            
            grouped = {}
            for n in m_notes:
                found_group = False
                for existing_tick in grouped.keys():
                    if abs(n['ticks'] - existing_tick) <= GROUPING_THRESHOLD_TICKS:
                        if n['char'] not in [en['char'] for en in grouped[existing_tick]]:
                            grouped[existing_tick].append(n)
                        found_group = True
                        break
                if not found_group:
                    grouped[n['ticks']] = [n]
            self.measures.append(grouped)

    def draw_stave(self, y_center):
        """오선지 그리기"""
        for i in range(5):
            line_y = y_center - 40 + i * 20
            pygame.draw.line(self.screen, (210, 210, 215), (40, line_y), (WIDTH - 40, line_y), 2)

    def render_measure(self, measure_idx, y_offset, display_ticks):
        """특정 마디를 지정된 Y 오프셋에 렌더링"""
        if measure_idx < 0 or measure_idx >= len(self.measures):
            return

        measure = self.measures[measure_idx]
        self.draw_stave(y_offset)
        
        # 마디 번호
        m_txt = self.small_font.render(f"M. {measure_idx + 1}", True, (180, 180, 190))
        self.screen.blit(m_txt, (45, y_offset - 70))
        
        for ticks, notes in measure.items():
            rel_ticks = ticks % self.ticks_per_measure
            x_pos = 70 + (rel_ticks / self.ticks_per_measure) * (WIDTH - 140)
            
            is_active = self.is_playing and abs(display_ticks - ticks) < 40
            note_color = RED if is_active else BLACK
            label_color = YELLOW if is_active else (60, 60, 65)
            
            # 음표
            for n in notes:
                note_y = y_offset - (n['note'] - 65) * 4.5
                pygame.draw.circle(self.screen, note_color, (int(x_pos), int(note_y)), 10)
            
            # 계명 텍스트
            for idx, n in enumerate(notes):
                char = n['char']
                char_y = y_offset + 90 + (idx * 45)
                txt_surf = self.font.render(char, True, label_color)
                text_rect = txt_surf.get_rect(center=(x_pos, char_y))
                self.screen.blit(txt_surf, text_rect)

        # 현재 연주 중인 마디라면 커서 그리기
        current_playing_m = int(display_ticks // self.ticks_per_measure)
        if self.is_playing and measure_idx == current_playing_m:
            rel_ticks_now = display_ticks % self.ticks_per_measure
            playhead_x = 70 + (rel_ticks_now / self.ticks_per_measure) * (WIDTH - 140)
            pygame.draw.line(self.screen, ORANGE, (playhead_x, y_offset - 50), (playhead_x, y_offset + 50), 4)

    def render(self):
        self.screen.fill(WHITE)
        
        display_ticks = self.current_ticks
        current_m_idx = int(display_ticks // self.ticks_per_measure)
        
        # 2마디 단위로 화면 그룹화 (0-1, 2-3, 4-5 ...)
        page_idx = current_m_idx // 2
        m1_idx = page_idx * 2
        m2_idx = m1_idx + 1
        
        # 첫 번째 마디 (위쪽)
        self.render_measure(m1_idx, HEIGHT // 2 - 180, display_ticks)
        # 두 번째 마디 (아래쪽)
        self.render_measure(m2_idx, HEIGHT // 2 + 180, display_ticks)

        # 상단 UI
        pygame.draw.rect(self.screen, GRAY, (0, 0, WIDTH, 140))
        pygame.draw.line(self.screen, (220, 225, 230), (0, 140), (WIDTH, 140), 2)
        
        file_title = os.path.basename(self.midi_path)
        title = self.title_font.render(file_title, True, BLACK)
        self.screen.blit(title, (30, 40))
        
        status_msg = "RECORDING (2-MEASURE MODE)" if self.is_playing else "PAUSED (SPACE)"
        status = self.small_font.render(status_msg, True, RED if self.is_playing else (120, 125, 130))
        self.screen.blit(status, (30, 75))
        
        sync_info = self.small_font.render(f"Sync: {self.audio_latency_ms}ms (UP/DOWN)", True, BLUE)
        self.screen.blit(sync_info, (30, 105))

        pygame.display.flip()

    def run(self):
        running = True
        while running:
            if self.is_playing:
                pos_ms = pygame.mixer.music.get_pos() + self.audio_latency_ms
                calc_ms = max(0, pos_ms)
                target_ticks = (calc_ms * self.ticks_per_beat) / 500.0 if calc_ms >= 0 else 0
                
                diff = target_ticks - self.current_ticks
                if abs(diff) > 1000: 
                    self.current_ticks = target_ticks
                else:
                    self.current_ticks += diff * 0.4
                
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_SPACE:
                        self.is_playing = not self.is_playing
                        if self.is_playing:
                            if pygame.mixer.music.get_pos() == -1:
                                pygame.mixer.music.play()
                                self.current_ticks = 0
                            else: pygame.mixer.music.unpause()
                        else: pygame.mixer.music.pause()
                    
                    if event.key == pygame.K_UP:
                        self.audio_latency_ms += 10
                        self.save_config()
                    if event.key == pygame.K_DOWN:
                        self.audio_latency_ms -= 10
                        self.save_config()

            self.render()
            self.clock.tick(FPS)
        pygame.quit()

def select_midi_file():
    root = tk.Tk()
    root.withdraw()
    file_path = filedialog.askopenfilename(
        title="Select MIDI File",
        filetypes=(("MIDI files", "*.mid *.midi"), ("All files", "*.*"))
    )
    root.destroy()
    return file_path

if __name__ == "__main__":
    selected_path = select_midi_file()
    if selected_path:
        player = MIDIPlayer(selected_path)
        player.run()