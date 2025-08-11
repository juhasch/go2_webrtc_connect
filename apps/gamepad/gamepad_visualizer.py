#!/usr/bin/env python3
import sys
import pygame
from pygame.locals import *

# Initialize pygame
pygame.init()

# Set up the window
WINDOW_WIDTH = 800
WINDOW_HEIGHT = 600
screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
pygame.display.set_caption('Gamepad Visualizer')

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
GRAY = (128, 128, 128)

# Fonts
font = pygame.font.SysFont('Arial', 24)
small_font = pygame.font.SysFont('Arial', 18)

def draw_button(screen, x, y, radius, pressed):
    """Draw a button with pressed/released state"""
    color = RED if pressed else GRAY
    pygame.draw.circle(screen, color, (x, y), radius)
    pygame.draw.circle(screen, BLACK, (x, y), radius, 2)

def draw_axis(screen, x, y, width, height, value, axis_name):
    """Draw an axis representation with its value"""
    # Draw axis background
    pygame.draw.rect(screen, GRAY, (x, y, width, height))
    pygame.draw.rect(screen, BLACK, (x, y, width, height), 2)
    
    # Calculate fill based on axis value (-1 to 1)
    if value >= 0:
        # Draw right/down
        fill_width = int(width * value / 2)
        pygame.draw.rect(screen, GREEN, (x + width//2, y, fill_width, height))
    else:
        # Draw left/up
        fill_width = int(width * -value / 2)
        pygame.draw.rect(screen, BLUE, (x + width//2 - fill_width, y, fill_width, height))
    
    # Draw center line
    pygame.draw.line(screen, BLACK, (x + width//2, y), (x + width//2, y + height), 2)
    
    # Draw axis label to the left of the bar
    label_text = small_font.render(f"{axis_name}:", True, WHITE)
    screen.blit(label_text, (x - 80, y + height//2 - 9))
    
    # Draw axis value to the right of the bar
    value_text = small_font.render(f"{value:.2f}", True, WHITE)
    screen.blit(value_text, (x + width + 10, y + height//2 - 9))

def main():
    clock = pygame.time.Clock()
    
    # Initialize joystick
    pygame.joystick.init()
    
    # Check if any gamepad is connected
    if pygame.joystick.get_count() == 0:
        print("No gamepad detected. Please connect a gamepad.")
        pygame.quit()
        sys.exit()
    
    # Get the first gamepad
    joystick = pygame.joystick.Joystick(0)
    joystick.init()
    
    # Get gamepad name
    gamepad_name = joystick.get_name()
    
    # Get number of axes, buttons, etc.
    num_axes = joystick.get_numaxes()
    num_buttons = joystick.get_numbuttons()
    num_hats = joystick.get_numhats()
    
    print(f"Gamepad: {gamepad_name}")
    print(f"Axes: {num_axes}")
    print(f"Buttons: {num_buttons}")
    print(f"Hats: {num_hats}")
    
    running = True
    while running:
        # Handle events
        for event in pygame.event.get():
            if event.type == QUIT:
                running = False
            elif event.type == KEYDOWN:
                if event.key == K_ESCAPE:
                    running = False
        
        # Clear screen
        screen.fill(BLACK)
        
        # Draw gamepad info
        text = font.render(f"Gamepad: {gamepad_name}", True, WHITE)
        screen.blit(text, (20, 20))
        
        # Draw axes
        axis_width = 300
        axis_height = 30
        axis_spacing = 50
        axis_x = 100  # Increased x position to make room for labels
        
        for i in range(min(num_axes, 6)):  # Display up to 6 axes
            axis_value = joystick.get_axis(i)
            axis_y = 80 + i * axis_spacing
            draw_axis(screen, axis_x, axis_y, axis_width, axis_height, axis_value, f"Axis {i}")
        
        # Draw buttons
        button_x_start = 550  # Moved buttons further to the right
        button_y_start = 100
        button_radius = 15
        button_spacing_x = 50  # Increased from 40 to 50 for more space between buttons
        button_spacing_y = 60  # Increased from 20 to 30 for more space between rows
        buttons_per_row = 5
        
        for i in range(min(num_buttons, 16)):  # Display up to 16 buttons
            button_pressed = joystick.get_button(i)
            row = i // buttons_per_row
            col = i % buttons_per_row
            button_x = button_x_start + col * button_spacing_x
            button_y = button_y_start + row * button_spacing_y
            draw_button(screen, button_x, button_y, button_radius, button_pressed)
            
            # Draw button label below the button with more space
            text = small_font.render(str(i), True, WHITE)
            text_rect = text.get_rect(center=(button_x, button_y + button_radius + 15))  # Increased from 10 to 15
            screen.blit(text, text_rect)
        
        # Draw D-pad (hat)
        if num_hats > 0:
            hat_x = 550  # Moved D-pad further to the right
            hat_y = 350
            hat_size = 100
            hat_value = joystick.get_hat(0)  # Get first hat
            
            # Draw D-pad background
            pygame.draw.rect(screen, GRAY, (hat_x, hat_y, hat_size, hat_size))
            pygame.draw.rect(screen, BLACK, (hat_x, hat_y, hat_size, hat_size), 2)
            
            # Draw D-pad directions
            # Up
            up_color = RED if hat_value[1] > 0 else GRAY
            pygame.draw.polygon(screen, up_color, [
                (hat_x + hat_size//2, hat_y), 
                (hat_x + hat_size//4, hat_y + hat_size//3),
                (hat_x + hat_size*3//4, hat_y + hat_size//3)
            ])
            
            # Down
            down_color = RED if hat_value[1] < 0 else GRAY
            pygame.draw.polygon(screen, down_color, [
                (hat_x + hat_size//2, hat_y + hat_size), 
                (hat_x + hat_size//4, hat_y + hat_size*2//3),
                (hat_x + hat_size*3//4, hat_y + hat_size*2//3)
            ])
            
            # Left
            left_color = RED if hat_value[0] < 0 else GRAY
            pygame.draw.polygon(screen, left_color, [
                (hat_x, hat_y + hat_size//2), 
                (hat_x + hat_size//3, hat_y + hat_size//4),
                (hat_x + hat_size//3, hat_y + hat_size*3//4)
            ])
            
            # Right
            right_color = RED if hat_value[0] > 0 else GRAY
            pygame.draw.polygon(screen, right_color, [
                (hat_x + hat_size, hat_y + hat_size//2), 
                (hat_x + hat_size*2//3, hat_y + hat_size//4),
                (hat_x + hat_size*2//3, hat_y + hat_size*3//4)
            ])
            
            # Display hat value
            text = small_font.render(f"D-pad: {hat_value}", True, WHITE)
            screen.blit(text, (hat_x, hat_y + hat_size + 10))
        
        # Display instructions
        text = small_font.render("Press ESC to quit", True, WHITE)
        screen.blit(text, (WINDOW_WIDTH - 150, WINDOW_HEIGHT - 30))
        
        pygame.display.flip()
        clock.tick(60)
    
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main() 