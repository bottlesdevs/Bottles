import curses
import random
import time
import sys
import os


class Snake:
    def __init__(self, stdscr: curses.window):
        self.__is_running = None
        self.stdscr = stdscr
        self.stdscr.nodelay(True)
        self.stdscr.timeout(0)
        curses.curs_set(0)
        curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)
        curses.init_pair(2, curses.COLOR_YELLOW, curses.COLOR_BLACK)
        curses.init_pair(3, curses.COLOR_BLACK, curses.COLOR_WHITE)

        self.snake = [[4, 10], [4, 9], [4, 8]]
        self.food = [0, 0]
        self.score = 0
        self.life = 3
        self.direction = 'RIGHT'

        self.generate_food()

    def generate_food(self):
        self.food = [int(random.random() * 20), int(random.random() * 20)]
        while self.food in self.snake:
            bounds = self.stdscr.getmaxyx()
            self.food = [int(random.random() * (bounds[0] - 2)) + 1, int(random.random() * (bounds[1] - 2)) + 1]

    def draw(self):
        self.stdscr.clear()
        self.stdscr.box()
        self.stdscr.addstr(
            self.stdscr.getmaxyx()[0] - 1, self.stdscr.getmaxyx()[1] // 2 - len(str(self.score)) // 2,
            f'Score: {self.score}',
            curses.color_pair(3)
        )

        for i, j in self.snake:
            try:
                self.stdscr.addstr(i, j, '◍', curses.color_pair(1))
            except:
                self.__is_running = False

        self.stdscr.addstr(self.food[0], self.food[1], '🍎', curses.color_pair(2))
        self.stdscr.refresh()

    def move(self):
        new_head = [self.snake[0][0], self.snake[0][1]]

        if self.direction == 'UP':
            new_head[0] -= 1
        elif self.direction == 'DOWN':
            new_head[0] += 1
        elif self.direction == 'LEFT':
            new_head[1] -= 1
        elif self.direction == 'RIGHT':
            new_head[1] += 1

        self.snake.insert(0, new_head)

        if self.snake[0] == self.food:
            self.score += 1
            self.generate_food()
        else:
            self.snake.pop()

    def get_input(self):
        key = self.stdscr.getch()
        if key == curses.KEY_UP and self.direction != 'DOWN':
            self.direction = 'UP'
        elif key == curses.KEY_DOWN and self.direction != 'UP':
            self.direction = 'DOWN'
        elif key == curses.KEY_LEFT and self.direction != 'RIGHT':
            self.direction = 'LEFT'
        elif key == curses.KEY_RIGHT and self.direction != 'LEFT':
            self.direction = 'RIGHT'
        elif key == ord('q'):
            exit()

    def get_result(self):
        return f'Your score is {self.score}'

    def run(self):
        self.__is_running = True
        while self.__is_running:
            self.get_input()
            self.move()
            self.draw()
            time.sleep(0.1)


result = "Game over!"


def main(stdscr):
    global result
    snake = Snake(stdscr)
    snake.run()
    result = snake.get_result()


if __name__ == '__main__':
    os.system('clear')
    logo = """
.▄▄ ·  ▐ ▄  ▄▄▄· ▄ •▄ ▄▄▄ .
▐█ ▀. •█▌▐█▐█ ▀█ █▌▄▌▪▀▄.▀·
▄▀▀▀█▄▐█▐▐▌▄█▀▀█ ▐▀▀▄·▐▀▀▪▄
▐█▄▪▐███▐█▌▐█ ▪▐▌▐█.█▌▐█▄▄▌
 ▀▀▀▀ ▀▀ █▪ ▀  ▀ ·▀  ▀ ▀▀▀ 
"""
    print(logo)
    print('\u2550' * 27)
    print("""
1. Play
2. Exit
""")
    print('\u2550' * 27)
    print("\nDo you want to play a game? (1/2)\n")
    choice = input()
    if choice == '1':
        curses.wrapper(main)
        os.system('tput reset')

        print('\u2554' + '\u2550' * (len(result) + 2) + '\u2557')
        print('\u2551' + " " + result + " " + '\u2551')
        print('\u255a' + '\u2550' * (len(result) + 2) + '\u255d')
        print("Start again? (y/n)")

        if input() == 'y':
            os.execl(sys.executable, os.path.abspath(__file__), *sys.argv)
        else:
            exit()
    elif choice == '2':
        exit()
