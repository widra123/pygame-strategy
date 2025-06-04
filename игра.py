import pygame
import sys

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

try:
    shoot_sound = pygame.mixer.Sound("shoot.wav")
    hit_sound = pygame.mixer.Sound("hit.wav")
except pygame.error as e:
    print("Ошибка загрузки звуков:", e)
    shoot_sound = None
    hit_sound = None

# Загрузка текстур врага и пули
try:
    enemy_image = pygame.image.load("enemy.png").convert_alpha()
except pygame.error:
    print("Не удалось загрузить текстуру врага")
    enemy_image = None

try:
    bullet_image = pygame.image.load("bullet.png").convert_alpha()
except pygame.error:
    print("Не удалось загрузить текстуру пули")
    bullet_image = None

MENU = "menu"
PLAYING = "playing"
game_state = MENU

CELL_SIZE = 50

grid_surface = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
grid_surface.fill((0, 0, 0, 0))

# ВОЛНЫ И СПАВН ВРАГОВ
wave = 0
wave_in_progress = False
enemies_to_spawn = 0
spawned_enemies = 0
spawn_interval = 30  # кадров между спавном врагов
spawn_timer = 0
wave_break = 180  # время между волнами, если волна закончилась (кадры)
wave_break_timer = 0

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
            if self.rect.collidepoint(event.pos):
                return True
        return False

def get_start_button():
    return Button("Начать игру", WIDTH // 2 - 100, HEIGHT // 2 - 30, 200, 60, GRAY, BLUE)

start_button = get_start_button()

def cell_center(cx, cy):
    return cx * CELL_SIZE + CELL_SIZE // 2, cy * CELL_SIZE + CELL_SIZE // 2

path_cells = [
    (0, 12),
    (3, 12),
    (3, 9),
    (6, 9),
    (6, 11),
    (9, 11),
    (9, 6),
    (12, 6),
    (12, 10),
    (15, 10),
    (15, 13),
    (12, 13),
    (12, 18),
    (17, 18),
    (17, 14),
    (20, 14)
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
        health_percent = self.health / self.max_health
        pygame.draw.rect(surface, RED, (self.x - hbw/2, self.y - self.radius - 15, hbw, hbh))
        pygame.draw.rect(surface, GREEN, (self.x - hbw/2, self.y - self.radius - 15, hbw * health_percent, hbh))

class Tower:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.size = CELL_SIZE
        self.range = CELL_SIZE * 3
        self.damage = 20
        self.reload_time = 30
        self.reload_counter = 0
        self.level = 1  # уровень башни
        self.upgrade_cost = 50  # стоимость следующего улучшения

    def draw(self, surface, highlight=False):
        rect = pygame.Rect(0, 0, self.size, self.size)
        rect.center = (self.x, self.y)
        border_rect = rect.inflate(4, 4)
        pygame.draw.rect(surface, BLACK, border_rect)
        pygame.draw.rect(surface, BLUE, rect)
        if highlight:
            pygame.draw.rect(surface, YELLOW, rect, 3)

    def can_shoot(self):
        return self.reload_counter == 0

    def shoot(self, enemies, bullets):
        for enemy in enemies:
            dist = ((enemy.x - self.x) ** 2 + (enemy.y - self.y) ** 2) ** 0.5
            if dist <= self.range:
                if self.can_shoot():
                    if shoot_sound:
                        shoot_sound.play()
                    bullets.append(Bullet(self.x, self.y, enemy))
                    self.reload_counter = self.reload_time
                break

    def update(self):
        if self.reload_counter > 0:
            self.reload_counter -= 1

    def upgrade(self):
        if self.level < 5:
            self.level += 1
            self.damage = int(self.damage * 1.5)
            self.range = int(self.range * 1.2)
            self.reload_time = max(5, int(self.reload_time * 0.8))
            self.upgrade_cost = int(self.upgrade_cost * 1.5)
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
        distance = (vector_x ** 2 + vector_y ** 2) ** 0.5
        if distance <= self.speed or distance == 0:
            self.target.health -= self.damage
            if hit_sound:
                hit_sound.play()
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
    grid_surface.fill((0, 0, 0, 0))
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
    alpha_surf = pygame.Surface((radius*2, radius*2), pygame.SRCALPHA)
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
        lines.append(f"Стоимость улучшения: {tower.upgrade_cost}")
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
    enemies_to_spawn = 5 + wave * 3
    spawned_enemies = 0
    spawn_timer = 0

def game_loop():
    global lives, money, selected_tower_for_info
    global wave_in_progress, enemies_to_spawn, spawned_enemies, spawn_timer, wave_break_timer

    screen.fill(WHITE)

    draw_path(screen, path)

    if wave_in_progress:
        spawn_timer += 1
        if spawn_timer >= spawn_interval and spawned_enemies < enemies_to_spawn:
            enemies.append(Enemy(path))
            spawned_enemies += 1
            spawn_timer = 0

        if spawned_enemies == enemies_to_spawn and len(enemies) == 0:
            wave_in_progress = False
            wave_break_timer = 0
    else:
        wave_break_timer += 1
        if wave_break_timer >= wave_break:
            start_wave()

    for enemy in enemies[:]:
        if not enemy.move():
            lives -= 1
            enemies.remove(enemy)
        elif not enemy.alive:
            enemies.remove(enemy)
            money += 10

    for tower in towers:
        tower.update()
        tower.shoot(enemies, bullets)

    for bullet in bullets[:]:
        bullet.move()
        if not bullet.alive:
            bullets.remove(bullet)

    for enemy in enemies:
        enemy.draw(screen)
    for tower in towers:
        highlight = (tower == selected_tower_for_info)
        tower.draw(screen, highlight=highlight)
    for bullet in bullets:
        bullet.draw(screen)

    draw_grid(screen)

    lives_text = font.render(f"Жизни: {lives}", True, BLACK)
    money_text = font.render(f"Деньги: {money}", True, BLACK)
    wave_text = font.render(f"Волна: {wave}", True, BLACK)
    screen.blit(lives_text, (10, 10))
    screen.blit(money_text, (10, 50))
    screen.blit(wave_text, (10, 90))

    instructions_text = font.render(
        "ЛКМ: поставить башню (-50), ПКМ: инфо по башне, двойной ПКМ: улучшить башню (растущая стоимость)",
        True, BLACK)
    screen.blit(instructions_text, (10, HEIGHT - 40))

    if selected_tower_for_info is not None:
        draw_tower_info(screen, selected_tower_for_info)

    pygame.display.flip()

def main():
    global game_state, money, lives, towers, enemies, bullets
    global wave, wave_in_progress, enemies_to_spawn, spawned_enemies, spawn_timer, wave_break_timer
    global WIDTH, HEIGHT, screen, start_button, selected_tower_for_info

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
    double_click_interval = 400  # мс

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            if event.type == pygame.VIDEORESIZE:
                WIDTH, HEIGHT = event.w, event.h
                screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
                start_button = get_start_button()

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
                    start_wave()

            elif game_state == PLAYING:
                if event.type == pygame.MOUSEBUTTONDOWN:
                    mx, my = pygame.mouse.get_pos()
                    grid_x_index = mx // CELL_SIZE
                    grid_y_index = my // CELL_SIZE

                    if event.button == 1:  # ЛКМ - ставим башню
                        if (grid_x_index, grid_y_index) in path_cells:
                            continue

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

                    elif event.button == 3:  # ПКМ - инфо или улучшение башни
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
                                # Улучшаем башню, если хватает денег
                                if money >= clicked_tower.upgrade_cost:
                                    success = clicked_tower.upgrade()
                                    if success:
                                        money -= clicked_tower.upgrade_cost
                                # Иначе не хватает денег — просто игнорируем или можно добавить сообщение
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

        clock.tick(60)

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
