import pygame
import random
import os
import neat
import pickle

# Initialize Pygame
pygame.init()

# Set window dimensions
w, h = 500, 500

# Create Pygame window
win = pygame.display.set_mode((w, h))
pygame.display.set_caption("AI BRICK BREAKER")

# Set font for displaying text
font = pygame.font.SysFont("comicsans", 30)

# Create clock object to control frame rate
clock = pygame.time.Clock()

# Class for the paddle object
class Paddle:
    def __init__(self):
        self.width = 100  # Increase paddle width
        self.height = 20
        self.x = (w - self.width) // 2
        self.y = h - 10 - self.height
        self.vel = 5
        self.currvel = 0  # for applying spin to ball
        self.breakable = False

    # Method to move the paddle based on user input
    def move(self, keys):
        if keys['left'] and self.x > 0:
            self.x -= self.vel
            self.currvel = -2
            if self.x < 0:
                self.x = 0
                self.currvel = 0
        if keys['right'] and self.x < w - self.width:
            self.x += self.vel
            self.currvel = 2
            if self.x > w - self.width:
                self.x = w - self.width
                self.currvel = 0

# Class for the brick object
class Brick:
    def __init__(self, x=0, y=0, boxIndex=0):
        self.width = 50
        self.height = 20
        self.x = x
        self.y = y
        self.currvel = 0  # only to avoid errors in collision detection
        self.breakable = True
        self.index = boxIndex

# Class for the ball object
class Ball:
    def __init__(self):
        self.radius = 8
        self.x = w // 2
        self.y = h - 150
        self.xvel = random.randrange(-3, 4, 2) # Initial x velocity of the ball
        self.yvel = -5
        self.softcap = 7

    # Method to move the ball and handle collisions with objects
    def move(self, box_obs):
        self.x += self.xvel
        self.y += self.yvel
        # make sure you actually collide for a single frame before changing direction
        if self.x < self.radius:
            self.x = self.radius
            self.xvel = -self.xvel
        if self.x > w - self.radius:
            self.x = w - self.radius
            self.xvel = -self.xvel
        if self.y < self.radius:
            self.y = self.radius
            self.yvel = -self.yvel

        x_cooldown, y_cooldown = 0, 0  # to prevent multiple collisions in a single axis in a single frame
        for box in box_obs:
            if y_cooldown == 1 and x_cooldown == 1:
                break  # exits early to save computation
            #collision from above
            if y_cooldown == 0 and 0 < box.y - self.y <= self.radius and box.x - self.radius/2 <= self.x <= box.x + box.width + self.radius/2:
                self.y = box.y - self.radius
                self.yvel = -self.yvel
                self.xvel += box.currvel
                if self.xvel > 0 and self.xvel > self.softcap:
                    self.xvel = self.softcap
                elif self.xvel < 0 and self.xvel < -self.softcap:
                    self.xvel = -self.softcap
                y_cooldown = 1  # so that it doesn't register multiple collisions in the same frame
                if box.breakable:
                    box_obs.pop(box_obs.index(box))
            #collision from below - only for bricks, not paddle, so no currvel
            elif y_cooldown == 0 and 0 < self.y - box.y - box.height <= self.radius and box.x - self.radius/2 <= self.x <= box.x + box.width + self.radius/2:
                #self.x -= int((self.xvel/abs(self.xvel))*(self.xvel/self.yvel)*(self.radius - self.y + box.y + box.height))
                self.y = box.y + box.height + self.radius
                self.yvel = -self.yvel
                y_cooldown = 1
                if box.breakable:
                    box_obs.pop(box_obs.index(box))
            #collision from left - not adding currvel for same reason
            elif x_cooldown == 0 and 0 < box.x - self.x <= self.radius and box.y - self.radius <= self.y <= box.y + box.height + self.radius:
                self.x = box.x - self.radius
                self.xvel = -self.xvel
                x_cooldown = 1
                if box.breakable:
                    box_obs.pop(box_obs.index(box))
            #collision from right - same as above
            elif x_cooldown == 0 and 0 < self.x - box.x - box.width <= self.radius and box.y - self.radius <= self.y <= box.y + box.height + self.radius:
                self.x = box.x + box.width + self.radius
                self.xvel = -self.xvel
                x_cooldown = 1
                if box.breakable:
                    box_obs.pop(box_obs.index(box))

        if self.y > h - 5:  # kill ball
            return 1
        return 0

# Global variable to track the generation number
gen = 0
fitness_scores = []  # To store fitness scores over generations

# Fitness function to evaluate the performance of each genome (neural network)
def fitness(genomes, config):
    global win, gen, fitness_scores
    gen += 1
    nets = []
    agents = []
    ge = []
    for genome_id, genome in genomes:
        genome.fitness = 0
        net = neat.nn.FeedForwardNetwork.create(genome, config)
        nets.append(net)
        agents.append(Paddle())
        ge.append(genome)

    for index in range(len(nets)):
        paddle = agents[index]
        running = True
        box_obs = [paddle]
        brick_y = 80
        def_brick_w = Brick().width
        def_brick_h = Brick().height
        boxIndex = 0
        for _ in range(5):
            brick_x = 0
            for _ in range((w // Brick().width)):
                box_obs.append(Brick(brick_x, brick_y, boxIndex))
                boxIndex += 1
                brick_x += def_brick_w
            brick_y += def_brick_h
        ball = Ball()
        dead_ball = 0
        start_ticks = pygame.time.get_ticks()  # to prevent infinite loop, break after 200 seconds
        paddle_bonus = 0
        while running:
            clock.tick(1000)  # sets highest fps possible for fastest training
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                    pygame.quit()
                    quit()
                    break
            paddle.currvel = 0
            keys = {'left': False, 'right': False}
            # input for NEAT will be the following + 1 or 0 for each brick that's unbroken/broken in order.
            inputList = [paddle.x, paddle.y, ball.x, ball.y, ball.xvel, ball.yvel]
            brokenList = [0] * boxIndex
            for box in box_obs[1:]:
                brokenList[box.index] = 1
            inputList.extend(brokenList)
            output = nets[index].activate(tuple(inputList))
            if output[0] > 0.5:
                keys['left'] = True
            elif output[1] > 0.5:
                keys['right'] = True
            paddle.move(keys)
            dead_ball = ball.move(box_obs)
            score = 51 - len(box_obs)
            if score < 5 and paddle.y == ball.y + ball.radius and paddle.x - ball.radius/2 <= ball.x <= paddle.x + paddle.width + ball.radius/2:
                paddle_bonus += 0.8
            ge[index].fitness = score + paddle_bonus
            if dead_ball:
                ge[index].fitness -= abs(ball.x - paddle.x)/50
                if score == 1:
                    ge[index].fitness -= 5
                running = False

            win.fill((0, 0, 0))  # Change background color to black
            pygame.draw.rect(win, (255, 0, 0), (paddle.x, paddle.y, paddle.width, paddle.height))  # Change paddle color to red
            pygame.draw.circle(win, (0, 255, 0), (ball.x, ball.y), ball.radius)  # Change ball color to green
            for brick in box_obs[1:]:
                pygame.draw.rect(win, (0, 0, 255), (brick.x + 1, brick.y + 1, brick.width - 2, brick.height - 2))
            score_label = font.render("Score: " + str(score), 1, (255, 255, 255))
            win.blit(score_label, (10, 10))
            gen_label = font.render("Gen: " + str(gen) + " Species: " + str(index+1), 1, (255, 255, 255))
            win.blit(gen_label, (w - gen_label.get_width() - 10, 10))
            pygame.display.update()

            if score >= 50 and dead_ball:  # stops training when score reaches 50
                print("Training stopped at generation", gen, "with score", score)
                return

            if (pygame.time.get_ticks() - start_ticks)/1000 > 20:
                ge[index].fitness -= 8
                running = False
                print("Infinite loop occurred")
                break

        # Append fitness score for this generation
        fitness_scores.append(ge[index].fitness)

# Function to execute the NEAT algorithm for training
def run(config_file):
    config = neat.config.Config(neat.DefaultGenome, neat.DefaultReproduction,
                                neat.DefaultSpeciesSet, neat.DefaultStagnation,
                                config_file)
    population = neat.Population(config)

    population.add_reporter(neat.StdOutReporter(True))
    stats = neat.StatisticsReporter()
    population.add_reporter(stats)
    winner = population.run(fitness, 20)

    print('\nBest genome:\n{!s}'.format(winner))

    # Print statistics
    print("\n--- Statistics ---")
    print("Generation:", gen)
    print("Fitness Scores:", fitness_scores)

# Main function to execute the training process
if __name__ == '__main__':
    local_dir = os.path.dirname(__file__)
    config_path = os.path.join(local_dir, 'NEAT_config.txt')
    run(config_path)
