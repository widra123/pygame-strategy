import pygame
import sys
import os
import math
import random

pygame.init()
pygame.mixer.init()

infoObject = pygame.display.Info()
WIDTH, HEIGHT = infoObject.current_w, infoObject.current_h

screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
pygame.display.set_caption("Tower Defense")

WHITE = (255, 255, 255)
GRAY = (50, 50, 50)
GREEN = (0, 255, 0)
RED = (255, 0, 0)
BLACK = (0, 0, 0)
BLUE = (0, 0, 255)
YELLOW = (255, 255, 0)

font = pygame.font.SysFont(None, 40)
info_font = pygame.font.SysFont(None, 24)

SOUNDS_DIR = os.path.join("sounds")
TEXTURES_DIR = os.path.join("textures")

CHANNELS_COUNT = 8
pygame.mixer.set_num_channels(CHANNELS_COUNT)
channels = [pygame.mixer.Channel(i) for i in range(CHANNELS_COUNT)]

def play_sound(sound):
    if sound is None:
        return
    for ch in channels:
        if not ch.get_busy():
            ch.play(sound)
            return
    channels[0].play(sound)

def load_sound(filename):
    path = os.path.join(SOUNDS_DIR, filename)
    if not os.path.isfile(path):
        print(f"Warning: sound file '{path}' not found!")
        return None
    try:
        return pygame.mixer.Sound(path)
    except pygame.error as e:
        print(f"Error loading sound {filename}: {e}")
        return None

def load_image(filename):
    path = os.path.join(TEXTURES_DIR, filename)
    if not os.path.isfile(path):
        print(f"Warning: image file '{path}' not found!")
        return None
    try:
        return pygame.image.load(path).convert_alpha()
    except pygame.error as e:
        print(f"Error loading image {filename}: {e}")
        return None

shoot_sound = load_sound("shoot.wav")
hit_sound = load_sound("hit.wav")
pause_on_sound = load_sound("pause_on.wav")    # Звук постановки на паузу
pause_off_sound = load_sound("pause_off.wav")  # Звук выхода из паузы

enemy_image = load_image("enemy.png")
fast_enemy_image = load_image("fast_enemy.png")  # для быстрого врага
boss_image = load_image("boss.png")
bullet_image = load_image("bullet.png")
tower_base_image = load_image("tower_base.png")
base_dulo_image = load_image("base_dulo.png")
fast_boss_image = load_image("fast_boss.png")

MENU = "menu"
PLAYING = "playing"
game_state = MENU

CELL_SIZE = 50

dev_console = False
console_input = ""

grid_surface = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
grid_surface.fill((0, 0, 0, 0))

wave = 0
wave_in_progress = False
enemies_to_spawn = 0
spawned_enemies = 0
spawn_interval = 30
spawn_timer = 0

wave_break = 5 * 60
wave_break_timer = 0

paused = False  # Для паузы

class Button:
    def __init__(self, text, x, y, w, h, color, hover_color):
        self.text = text
        self.rect = pygame.Rect(x, y, w, h)
        self.color = color
        self.hover_color = hover_color

    def draw(self, surface):
        mouse_pos = pygame.mouse.get_pos()
        if self.rect.collidepoint(mouse_pos):
            pygame.draw.rect(surface, self.hover_color, self.rect)
        else:
            pygame.draw.rect(surface, self.color, self.rect)
        text_surface = font.render(self.text, True, WHITE)
        text_rect = text_surface.get_rect(center=self.rect.center)
        surface.blit(text_surface, text_rect)

    def is_clicked(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            return self.rect.collidepoint(event.pos)
        return False

def get_start_button():
    return Button("Начать игру", WIDTH // 2 - 100, HEIGHT // 2 - 30, 200, 60, GRAY, BLUE)

start_button = get_start_button()

def get_start_wave_button():
    # Смещено чуть ниже (примерно +40 пикселей)
    return Button("Начать волну сейчас", 10, 150, 300, 50, GRAY, BLUE)

start_wave_button = get_start_wave_button()

def cell_center(cx, cy):
    return cx * CELL_SIZE + CELL_SIZE // 2, cy * CELL_SIZE + CELL_SIZE // 2

path_cells = [
    (0, 12), (1, 12), (2, 12), (3, 12), (3, 11), (3, 10), (3, 9),
    (4, 9), (5, 9), (6, 9), (6, 10), (6, 11), (7, 11), (8, 11),
    (9, 11), (9, 10), (9, 9), (9, 8), (9, 7), (9, 6), (10, 6),
    (11, 6), (12, 6), (12, 7), (12, 8), (12, 9), (12, 10), (13, 10),
    (14, 10), (15, 10), (15, 11), (15, 12), (15, 13), (14, 13),
    (13, 13), (12, 13), (12, 14), (12, 15), (12, 16), (12, 17),
    (12, 18), (13, 18), (14, 18), (15, 18), (16, 18), (17, 18),
    (18, 18), (19, 18), (20, 18), (21, 18), (22, 18), (23, 18),
    (24, 18), (25, 18),
]

def build_path_from_cells(cell_list):
    coords = []
    for cx, cy in cell_list:
        x, y = cell_center(cx, cy)
        coords.append((x, y))
    return coords

path = build_path_from_cells(path_cells)

lives = 10
money = 100

enemies = []
towers = []
bullets = []

selected_tower_for_info = None

class Enemy:
    def __init__(self, path):
        self.path = path
        self.pos_index = 0
        self.x, self.y = path[0]
        self.speed = 1
        self.health = 100
        self.max_health = 100
        self.radius = CELL_SIZE // 3
        self.alive = True
        self.image = enemy_image

    def move(self):
        if self.pos_index + 1 >= len(self.path):
            return False
        target_x, target_y = self.path[self.pos_index + 1]
        vector_x = target_x - self.x
        vector_y = target_y - self.y
        distance = (vector_x ** 2 + vector_y ** 2) ** 0.5
        if distance == 0:
            self.pos_index += 1
            return True
        dx = (vector_x / distance) * self.speed
        dy = (vector_y / distance) * self.speed
        if abs(dx) > abs(vector_x) and abs(dy) > abs(vector_y):
            self.x, self.y = target_x, target_y
            self.pos_index += 1
        else:
            self.x += dx
            self.y += dy
        return True

    def draw(self, surface):
        if self.image:
            rect = self.image.get_rect(center=(int(self.x), int(self.y)))
            surface.blit(self.image, rect)
        else:
            pygame.draw.circle(surface, RED, (int(self.x), int(self.y)), self.radius)
        hbw = CELL_SIZE * 0.6
        hbh = 6
        x = self.x - hbw / 2
        y = self.y - self.radius - 15
        # Рисуем контур (рамку)
        pygame.draw.rect(surface, BLACK, (x - 1, y - 1, hbw + 2, hbh + 2), 1)
        # Рисуем красный фон полоски
        pygame.draw.rect(surface, RED, (x, y, hbw, hbh))
        # Рисуем зелёную часть (здоровье)
        health_percent = self.health / self.max_health
        pygame.draw.rect(surface, GREEN, (x, y, hbw * health_percent, hbh))
    

class FastEnemy(Enemy):
    def __init__(self, path):
        super().__init__(path)
        self.speed = 2.0
        self.health = 100
        self.max_health = 100
        self.radius = CELL_SIZE // 3
        self.image = fast_enemy_image if fast_enemy_image else enemy_image

class BossEnemy(Enemy):
    def __init__(self, path):
        super().__init__(path)
        self.speed = 1.0
        base_health = 800 + 200 * (wave // 5)
        # Сделаем босса примерно в 2 раза слабее, уменьшив множитель с 2.5 на 1.2
        self.health = int(base_health * 1.2)
        self.max_health = self.health
        self.radius = CELL_SIZE
        self.image = boss_image

    def move(self):
        return super().move()
    
class FastBossEnemy(Enemy):
    def __init__(self, path, wave):
        super().__init__(path)
        self.speed = 2.0
        base_health = 800 + 200 * (wave // 5)
        self.health = int(base_health * 0.8)
        self.max_health = self.health
        self.radius = CELL_SIZE
        self.image = fast_boss_image
        if wave % 5 == 0 and spawned_enemies == enemies_to_spawn - 1:
            if wave >= 10:  # быстрый босс только с 10-й волны
                # 80% шанс создать быстрого босса
                if random.random() < 0.8:
                    enemies.append(FastBossEnemy(path))
                else:
                    enemies.append(BossEnemy(path))
            else:
                # На 5-й волне только обычный босс
                enemies.append(BossEnemy(path))
        
class Tower:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.size = CELL_SIZE
        self.range = CELL_SIZE * 3   # Дальность 3 клетки
        self.damage = 15             # Урон 15
        self.reload_time = 35        # Перезарядка 35 кадров
        self.reload_counter = 0
        self.level = 1
        self.upgrade_cost = 50
        self.upgrade_increment = 25
        self.first_upgrade_done = False
        self.current_target = None

    def draw(self, surface, highlight=False):
        rect = pygame.Rect(0, 0, self.size, self.size)
        rect.center = (self.x, self.y)
        border_rect = rect.inflate(4, 4)
        pygame.draw.rect(surface, BLACK, border_rect)

        if tower_base_image:
            img_rect = tower_base_image.get_rect(center=(self.x, self.y))
            surface.blit(tower_base_image, img_rect)
        else:
            pygame.draw.rect(surface, BLUE, rect)

        if highlight:
            pygame.draw.rect(surface, YELLOW, rect, 3)

    def draw_turret_barrel(self, surface):
        if base_dulo_image:
            image = base_dulo_image
            angle = 0
            if self.current_target and self.current_target.alive:
                dx = self.current_target.x - self.x
                dy = self.current_target.y - self.y
                angle = -math.degrees(math.atan2(dy, dx))
            rotated_image = pygame.transform.rotate(image, angle)
            rotated_rect = rotated_image.get_rect(center=(self.x, self.y))
            surface.blit(rotated_image, rotated_rect)

    def can_shoot(self):
        return self.reload_counter == 0

    def shoot(self, enemies, bullets):
        target = None
        max_progress = -1
        max_progress_dist = -1

        for enemy in enemies:
            dist = math.hypot(enemy.x - self.x, enemy.y - self.y)
            if dist <= self.range:
                if enemy.pos_index + 1 < len(enemy.path):
                    next_pt = enemy.path[enemy.pos_index + 1]
                    cur_pt = enemy.path[enemy.pos_index]
                    segment_len = math.hypot(next_pt[0] - cur_pt[0], next_pt[1] - cur_pt[1])
                    if segment_len != 0:
                        dist_to_next = math.hypot(next_pt[0] - enemy.x, next_pt[1] - enemy.y)
                        progress_frac = 1 - (dist_to_next / segment_len)
                    else:
                        progress_frac = 0
                else:
                    progress_frac = 0

                progress = enemy.pos_index + progress_frac

                if progress > max_progress or (math.isclose(progress, max_progress) and dist < max_progress_dist):
                    max_progress = progress
                    max_progress_dist = dist
                    target = enemy

        if target:
            self.current_target = target
            if self.can_shoot():
                if shoot_sound:
                    play_sound(shoot_sound)
                bullet = Bullet(self.x, self.y, target)
                bullet.damage = self.damage
                bullets.append(bullet)
                self.reload_counter = self.reload_time
        else:
            self.current_target = None

    def update(self):
        if self.reload_counter > 0:
            self.reload_counter -= 1

    def upgrade(self):
        if self.level < 5:
            self.level += 1
            if self.level < 5:
                self.damage = int(self.damage * 1.2)
                self.range = int(self.range * 1.1)
                self.reload_time = max(5, int(self.reload_time * 0.9))
            else:
                self.damage = int(self.damage * 2.0)
                self.range = int(self.range * 1.5)
                self.reload_time = max(3, int(self.reload_time * 0.7))
            return True
        return False

class Bullet:
    def __init__(self, x, y, target):
        self.x = x
        self.y = y
        self.speed = 6
        self.target = target
        self.radius = 5
        self.damage = 20
        self.alive = True
        self.image = bullet_image

    def move(self):
        if not self.target.alive:
            self.alive = False
            return

        vector_x = self.target.x - self.x
        vector_y = self.target.y - self.y
        distance = math.hypot(vector_x, vector_y)
        if distance <= self.speed:
            self.target.health -= self.damage
            if hit_sound:
                play_sound(hit_sound)
            if self.target.health <= 0:
                self.target.alive = False
            self.alive = False
        else:
            self.x += (vector_x / distance) * self.speed
            self.y += (vector_y / distance) * self.speed

    def draw(self, surface):
        if self.image:
            rect = self.image.get_rect(center=(int(self.x), int(self.y)))
            surface.blit(self.image, rect)
        else:
            pygame.draw.circle(surface, BLACK, (int(self.x), int(self.y)), self.radius)

def draw_grid(surface):
    global grid_surface
    if grid_surface.get_size() != (WIDTH, HEIGHT):
        grid_surface = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    grid_surface.fill((0,0,0,0))
    color = (200, 200, 200, 80)

    for x in range(0, WIDTH, CELL_SIZE):
        pygame.draw.line(grid_surface, color, (x, 0), (x, HEIGHT))
    for y in range(0, HEIGHT, CELL_SIZE):
        pygame.draw.line(grid_surface, color, (0, y), (WIDTH, y))

    surface.blit(grid_surface, (0, 0))

def draw_path(surface, path):
    if len(path) > 1:
        pygame.draw.lines(surface, BLACK, False, path, 5)

def draw_tower_info(surface, tower):
    radius = tower.range
    alpha_surf = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
    pygame.draw.circle(alpha_surf, (0, 0, 255, 70), (radius, radius), radius)
    surface.blit(alpha_surf, (tower.x - radius, tower.y - radius))

    info_width, info_height = 240, 140
    offset_x = radius + 15
    offset_y = -info_height // 2 - 15
    x = tower.x + offset_x
    y = tower.y + offset_y

    rect = pygame.Rect(x, y, info_width, info_height)
    pygame.draw.rect(surface, GRAY, rect)
    pygame.draw.rect(surface, BLACK, rect, 2)

    lines = [
        f"Башня (уровень {tower.level}):",
        f"Урон: {tower.damage}",
        f"Дальность: {tower.range // CELL_SIZE} клеток",
        f"Перезарядка: {tower.reload_time / 60:.1f} сек"
    ]
    if tower.level < 5:
        upgrade_cost_text = f"Стоимость улучшения: {tower.upgrade_cost if tower.level < 4 else 200}"
        lines.append(upgrade_cost_text)
    else:
        lines.append("Максимальный уровень")

    for i, line in enumerate(lines):
        text_surf = info_font.render(line, True, WHITE)
        surface.blit(text_surf, (x + 10, y + 10 + i * 25))

def main_menu():
    screen.fill(WHITE)
    title_text = font.render("Tower Defense", True, BLACK)
    screen.blit(title_text, (WIDTH // 2 - title_text.get_width() // 2, HEIGHT // 4))
    start_button.draw(screen)
    pygame.display.flip()

def start_wave():
    global wave, wave_in_progress, enemies_to_spawn, spawned_enemies, spawn_timer
    wave += 1
    wave_in_progress = True
    enemies_to_spawn = 3 + wave * 2
    if wave % 5 == 0:
        enemies_to_spawn += 1
    spawned_enemies = 0
    spawn_timer = 0

def spawn_enemy_for_wave(wave, path):
    chance_fast_enemy = min(0.1 + 0.05 * wave, 0.5)
    if random.random() < chance_fast_enemy:
        enemy = FastEnemy(path)
    else:
        enemy = Enemy(path)
    # Увеличиваем здоровье обычных и быстрых врагов на 1.7 раза на каждой 10-й волне
    if wave % 10 == 0:
        enemy.health = int(enemy.health * 1.7)
        enemy.max_health = enemy.health
    return enemy

def game_loop():
    global lives, money, selected_tower_for_info
    global wave_in_progress, enemies_to_spawn, spawned_enemies, spawn_timer, wave_break_timer
    global paused

    screen.fill(WHITE)

    draw_path(screen, path)
    draw_grid(screen)

    if paused:
        dark_overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        dark_overlay.fill((0, 0, 0, 150))
        screen.blit(dark_overlay, (0, 0))

        pause_text = font.render("пауза", True, WHITE)
        screen.blit(pause_text, (WIDTH // 2 - pause_text.get_width() // 2,
                                 HEIGHT // 2 - pause_text.get_height() // 2))
        pygame.display.flip()
        return

    if wave_in_progress:
        spawn_timer += 1
        if spawn_timer >= spawn_interval and spawned_enemies < enemies_to_spawn:
            if wave % 5 == 0 and spawned_enemies == enemies_to_spawn - 1:
                enemies.append(BossEnemy(path))
            else:
                enemies.append(spawn_enemy_for_wave(wave, path))
            spawned_enemies += 1
            spawn_timer = 0

        if spawned_enemies == enemies_to_spawn and len(enemies) == 0:
            wave_in_progress = False
            wave_break_timer = 0
    else:
        wave_break_timer += 1
        if wave_break_timer >= wave_break:
            start_wave()

    for bullet in bullets[:]:
        bullet.move()
        if not bullet.alive:
            bullets.remove(bullet)

    for enemy in enemies[:]:
        if enemy.health <= 0 or not enemy.alive:
            enemies.remove(enemy)
            money += 10
        else:
            if not enemy.move():
                lives -= 1
                enemies.remove(enemy)

    for tower in towers:
        tower.update()
        tower.shoot(enemies, bullets)

    for enemy in enemies:
        enemy.draw(screen)
    for tower in towers:
        highlight = (tower == selected_tower_for_info)
        tower.draw(screen, highlight=highlight)

    for bullet in bullets:
        bullet.draw(screen)

    for tower in towers:
        tower.draw_turret_barrel(screen)

    # Отрисовка жизней, денег и волны
    lives_text = font.render(f"Жизни: {lives}", True, BLACK)
    money_text = font.render(f"Деньги: {money}", True, BLACK)
    wave_text = font.render(f"Волна: {wave}", True, BLACK)
    screen.blit(lives_text, (10, 10))
    screen.blit(money_text, (10, 50))
    screen.blit(wave_text, (10, 90))

    # Таймер до следующей волны (если волна не в процессе), смещён ниже надписей
    if not wave_in_progress:
        remaining_frames = max(wave_break - wave_break_timer, 0)
        remaining_seconds = remaining_frames // 60
        timer_text = font.render(f"Следующая волна через: {remaining_seconds} сек", True, BLACK)
        screen.blit(timer_text, (10, 113.5))

    # Кнопка "Начать волну сейчас" под надписями, чуть ниже таймера
    if not wave_in_progress and not paused:
        start_wave_button.draw(screen)


    hints = [
        "ЛКМ: поставить башню (-50)",
        "ПКМ: инфо по башне",
        "Двойной ПКМ: улучшить башню",
        "Рост цены на улучшение, max уровень 5",
        "P: пауза"
    ]

    padding = 10
    line_height = info_font.get_height()

    for i, hint in enumerate(hints):
        text_surf = info_font.render(hint, True, BLACK)
        x = 10
        y = HEIGHT - padding - line_height * (len(hints) - i)
        screen.blit(text_surf, (x, y))

    if selected_tower_for_info is not None:
        draw_tower_info(screen, selected_tower_for_info)

    pygame.display.flip()

def main():
    global game_state, money, lives, towers, enemies, bullets
    global wave, wave_in_progress, enemies_to_spawn, spawned_enemies, spawn_timer, wave_break_timer
    global WIDTH, HEIGHT, screen, start_button, selected_tower_for_info, paused
    global start_wave_button

    clock = pygame.time.Clock()
    running = True

    wave = 0
    wave_in_progress = False
    enemies_to_spawn = 0
    spawned_enemies = 0
    spawn_timer = 0
    wave_break_timer = 0

    last_right_click_time = 0
    last_clicked_tower = None
    double_click_interval = 400
    prev_paused_state = paused  # Для отслеживания смены паузы и звука

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            
            if event.type == pygame.VIDEORESIZE:
                WIDTH, HEIGHT = event.w, event.h
                screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
                start_button = get_start_button()
                start_wave_button = get_start_wave_button()

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_p and game_state == PLAYING:
                    paused = not paused
                    if paused:
                        play_sound(pause_on_sound)
                    else:
                        play_sound(pause_off_sound)

            if game_state == MENU:
                if start_button.is_clicked(event):
                    game_state = PLAYING
                    money = 100
                    lives = 10
                    towers = []
                    enemies = []
                    bullets = []
                    wave = 0
                    wave_in_progress = False
                    enemies_to_spawn = 0
                    spawned_enemies = 0
                    spawn_timer = 0
                    wave_break_timer = 0
                    selected_tower_for_info = None
                    last_right_click_time = 0
                    last_clicked_tower = None
                    paused = False
                    start_wave()
                    
            elif game_state == PLAYING:
                if not paused:
                    if event.type == pygame.MOUSEBUTTONDOWN:
                        mx, my = pygame.mouse.get_pos()
                        grid_x_index = mx // CELL_SIZE
                        grid_y_index = my // CELL_SIZE

                        # Проверка кнопки "Начать волну сейчас"
                        if not wave_in_progress:
                            if start_wave_button.is_clicked(event):
                                start_wave()
                                wave_break_timer = 0
                                continue

                        if event.button == 1:  # ЛКМ - установка башни
                            if (grid_x_index, grid_y_index) in path_cells:
                                continue  # Нельзя ставить на путь

                            grid_x = grid_x_index * CELL_SIZE + CELL_SIZE // 2
                            grid_y = grid_y_index * CELL_SIZE + CELL_SIZE // 2

                            can_place = True
                            for tower in towers:
                                if tower.x == grid_x and tower.y == grid_y:
                                    can_place = False
                                    break
                            if can_place and money >= 50:
                                towers.append(Tower(grid_x, grid_y))
                                money -= 50
                                selected_tower_for_info = None

                        elif event.button == 3:  # ПКМ - инфо / улучшение
                            clicked_tower = None
                            for tower in towers:
                                rect = pygame.Rect(0, 0, tower.size, tower.size)
                                rect.center = (tower.x, tower.y)
                                if rect.collidepoint(mx, my):
                                    clicked_tower = tower
                                    break

                            current_time = pygame.time.get_ticks()

                            if clicked_tower is not None:
                                if clicked_tower == last_clicked_tower and (current_time - last_right_click_time) <= double_click_interval:
                                    upgrade_price = 200 if clicked_tower.level == 4 else clicked_tower.upgrade_cost
                                    if money >= upgrade_price:
                                        success = clicked_tower.upgrade()
                                        if success:
                                            money -= upgrade_price
                                            if not clicked_tower.first_upgrade_done:
                                                clicked_tower.first_upgrade_done = True
                                            else:
                                                if clicked_tower.level < 4:
                                                    clicked_tower.upgrade_cost = min(200, clicked_tower.upgrade_cost + 25)
                                selected_tower_for_info = clicked_tower
                            else:
                                selected_tower_for_info = None

                            last_right_click_time = current_time
                            last_clicked_tower = clicked_tower

        if game_state == MENU:
            main_menu()
        elif game_state == PLAYING:
            game_loop()
            if lives <= 0:
                game_state = MENU
                selected_tower_for_info = None
                paused = False

        clock.tick(60)

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
