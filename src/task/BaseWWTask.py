import re
import time
from datetime import datetime, timedelta

import numpy as np

from ok import BaseTask, Logger, find_boxes_by_name, og, Box
from ok import CannotFindException
import cv2

logger = Logger.get_logger(__name__)
number_re = re.compile(r'^(\d+)$')
stamina_re = re.compile(r'^(\d+)/(\d+)$')


class BaseWWTask(BaseTask):
    map_zoomed = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pick_echo_config = self.get_global_config('Pick Echo Config')
        self.monthly_card_config = self.get_global_config('Monthly Card Config')
        self.next_monthly_card_start = 0
        self._logged_in = False
        self.bosses_pos = {
            'Bell-Borne Geochelone': [0, 0, False],
            'Dreamless': [0, 2, True],
            'Jue': [0, 3, True],
            'Hecate': [0, 4, True],
            'Fleurdelys': [0, 5, True],
            'Tempest Mephis': [0, 6, False],
            'Inferno Rider': [1, 0, False],
            'Impermanence Heron': [1, 1, False],
            'Lampylumen Myriad': [1, 2, False],
            'Feilian Beringal': [1, 3, False],
            'Mourning Aix': [1, 4, False],
            'Crownless': [1, 5, False],
            'Mech Abomination': [1, 6, False],
            'Thundering Mephis': [2, 0, False],
            'Fallacy of No Return': [2, 1, False],
            'Lorelei': [2, 2, False],
            'Sentry Construct': [2, 3, False],
            'Dragon of Dirge': [2, 4, False],
            'Nightmare: Feilian Beringal': [2, 5, False],
            'Nightmare: Impermanence Heron': [2, 6, False],
            'Nightmare: Thundering Mephis': [3, 0, False],
            'Nightmare: Tempest Mephis': [3, 1, False],
            'Nightmare: Crownless': [3, 2, False],
            'Nightmare: Inferno Rider': [3, 3, False],
            'Nightmare: Mourning Aix': [3, 4, False],
            'Nightmare: Lampylumen Myriad': [3, 5, False],
        }

    def zoom_map(self):
        if not self.map_zoomed:
            self.log_info('zoom map to max')
            self.map_zoomed = True
            self.send_key('m', after_sleep=1)
            for i in range(11):
                self.click(0.95, 0.29, after_sleep=0.1)
            self.send_key('esc', after_sleep=1)

    def validate(self, key, value):
        message = self.validate_config(key, value)
        if message:
            return False, message
        else:
            return True, None

    def absorb_echo_text(self, ignore_config=False):
        if (self.pick_echo_config.get('Use OCR') or self.ocr_lib == 'paddleocr' or ignore_config) and (
                self.game_lang == 'zh_CN' or self.game_lang == 'en_US'):
            return re.compile(r'(吸收|Absorb)')
        else:
            return None

    @property
    def absorb_echo_feature(self):
        return self.get_feature_by_lang('absorb')

    def get_feature_by_lang(self, feature):
        lang_feature = feature + '_' + self.game_lang
        if self.feature_exists(lang_feature):
            return lang_feature
        else:
            return None

    def set_check_monthly_card(self, next_day=False):
        if self.monthly_card_config.get('Check Monthly Card'):
            now = datetime.now()
            hour = self.monthly_card_config.get('Monthly Card Time')
            # Calculate the next 4 o'clock in the morning
            next_four_am = now.replace(hour=hour, minute=0, second=0, microsecond=0)
            if now >= next_four_am or next_day:
                next_four_am += timedelta(days=1)
            next_monthly_card_start_date_time = next_four_am - timedelta(seconds=30)
            # Subtract 1 minute from the next 4 o'clock in the morning
            self.next_monthly_card_start = next_monthly_card_start_date_time.timestamp()
            logger.info('set next monthly card start time to {}'.format(next_monthly_card_start_date_time))
        else:
            self.next_monthly_card_start = 0

    @property
    def f_search_box(self):
        f_search_box = self.get_box_by_name('pick_up_f_hcenter_vcenter')
        f_search_box = f_search_box.copy(x_offset=-f_search_box.width * 0.3,
                                         width_offset=f_search_box.width * 0.65,
                                         height_offset=f_search_box.height * 6,
                                         y_offset=-f_search_box.height * 5,
                                         name='search_dialog')
        return f_search_box

    def find_f_with_text(self, target_text=None):
        f = self.find_one('pick_up_f_hcenter_vcenter', box=self.f_search_box, threshold=0.8)
        if f and target_text:
            search_text_box = f.copy(x_offset=f.width * 5, width_offset=f.width * 7, height_offset=1.5 * f.height,
                                     y_offset=-0.8 * f.height, name='search_text_box')
            text = self.ocr(box=search_text_box, match=target_text, target_height=540)
            logger.debug(f'found f with text {text}, target_text {target_text}')
            if not text:
                return None
        return f

    def walk_to_box(self, find_function, time_out=30, end_condition=None):
        if not find_function():
            self.log_info('find_function not found, break')
            return False
        last_direction = None
        start = time.time()
        ended = False
        while time.time() - start < time_out:
            if end_condition:
                ended = end_condition()
                if ended:
                    break
            treasure_icon = find_function()
            if not treasure_icon:
                if not end_condition:
                    self.log_info('find_function not found, break')
                    break
                else:
                    self.next_frame()
                    continue
            x, y = treasure_icon.center()
            y = max(0, y - self.height_of_screen(0.05))
            next_direction = self.get_direction(x, y, self.width, self.height)
            if next_direction != last_direction:
                if last_direction:
                    self.send_key_up(last_direction)
                    self.sleep(0.02)
                last_direction = next_direction
                self.send_key_down(next_direction)
            self.next_frame()
        if last_direction:
            self.send_key_up(last_direction)
            self.sleep(0.02)
        if not end_condition:
            return last_direction is not None
        else:
            return ended

    def get_direction(self, location_x, location_y, screen_width, screen_height):
        """
        Determines the location (w, a, s, d) based on diagonals
        spanning the middle 2/3 of the screen width.
        Regions outside this middle strip default to left ('a') or right ('d').
        Args:
            location_x: The x-coordinate of the point.
            location_y: The y-coordinate of the point.
            screen_width: The width of the screen.
            screen_height: The height of the screen.
        Returns:
            A string "w", "a", "s", or "d".
        """
        # Prevent division by zero or invalid inputs
        if screen_width <= 0 or screen_height <= 0:
            # Return a default or raise an error, here returning middle-ish default
            return "a" if location_x < screen_width / 2 else "d"
        # --- Define the central strip ---
        strip_width = (2 / 3) * screen_width
        # Start x-coordinate of the strip (left edge)
        x_start = (screen_width - strip_width) / 2
        # End x-coordinate of the strip (right edge)
        x_end = x_start + strip_width
        # --- Handle points outside the strip ---
        if location_x < x_start:
            return "a"  # Point is in the left 1/6th of the screen
        elif location_x > x_end:
            return "d"  # Point is in the right 1/6th of the screen
        else:
            # --- Point is within the central strip ---
            # Calculate diagonals as if the strip (width = strip_width) was the full screen
            # Avoid division by zero if strip_width is effectively zero
            if strip_width < 1e-9: # Use tolerance for float comparison
                 return "a" if location_x < screen_width / 2 else "d"
            # Slope magnitude: rise (screen_height) / run (strip_width)
            slope = screen_height / strip_width
            # Adjusted Diagonal 1: From (x_start, 0) to (x_end, screen_height)
            # Equation: y - 0 = slope * (x - x_start)
            # Calculate y value on this diagonal *at the point's location_x*
            adj_diagonal1_y = slope * (location_x - x_start)
            # Adjusted Diagonal 2: From (x_end, 0) to (x_start, screen_height)
            # Equation: y - 0 = -slope * (x - x_end)
            # Calculate y value on this diagonal *at the point's location_x*
            adj_diagonal2_y = -slope * (location_x - x_end)
            # --- Apply original comparison logic using adjusted diagonals ---
            # Note: The original comments/logic might map differently than visual intuition.
            # We are strictly following the original code's comparison structure.
            if location_y < adj_diagonal1_y and location_y > adj_diagonal2_y:
                 # Below adjusted diag 1, Above adjusted diag 2 -> 'd' in original logic (Right wedge)
                return "d"
            elif location_y > adj_diagonal1_y and location_y < adj_diagonal2_y:
                 # Above adjusted diag 1, Below adjusted diag 2 -> 'a' in original logic (Left wedge)
                return "a"
            elif location_y < adj_diagonal1_y and location_y < adj_diagonal2_y:
                 # Below both adjusted diagonals -> 'w' in original logic (Top wedge)
                return "w"
            else: # location_y >= adj_diagonal1_y and location_y >= adj_diagonal2_y:
                 # Above both adjusted diagonals -> 's' in original logic (Bottom wedge)
                return "s"

    def find_treasure_icon(self):
        return self.find_one('treasure_icon', box=self.box_of_screen(0.1, 0.2, 0.9, 0.8), threshold=0.7)

    def click(self, x=-1, y=-1, move_back=False, name=None, interval=-1, move=True, down_time=0.01, after_sleep=0, key="left"):
        if x == -1 and y == -1:
            x = self.width_of_screen(0.5)
            y = self.height_of_screen(0.5)
            move = False
            down_time = 0.01
        else:
            down_time = 0.2
        return super().click(x, y, move_back, name, interval, move=move, down_time=down_time, after_sleep=after_sleep, key=key)

    def check_for_monthly_card(self):
        if self.should_check_monthly_card():
            start = time.time()
            logger.info(f'check_for_monthly_card start check')
            if self.in_combat():
                logger.info(f'check_for_monthly_card in combat return')
                return time.time() - start
            if self.in_team_and_world():
                logger.info(f'check_for_monthly_card in team send sleep until monthly card popup')
                monthly_card = self.wait_until(self.handle_monthly_card, time_out=120, raise_if_not_found=False)
                logger.info(f'wait monthly card end {monthly_card}')
                cost = time.time() - start
                return cost
        return 0

    def in_realm(self):
        illusive_realm_exit = self.find_one('illusive_realm_exit',
                                            use_gray_scale=False, threshold=0.5)
        return illusive_realm_exit is not None

    def walk_until_f(self, direction='w', time_out=0, raise_if_not_found=True, backward_time=0, target_text=None,
                     cancel=True):
        logger.info(f'walk_until_f direction {direction} target_text: {target_text}')
        if not self.find_f_with_text(target_text=target_text):
            if backward_time > 0:
                if self.send_key_and_wait_f('s', raise_if_not_found, backward_time, target_text=target_text):
                    logger.info('walk backward found f')
                    return True
            return self.send_key_and_wait_f(direction, raise_if_not_found, time_out,
                                            target_text=target_text) and self.sleep(0.5)
        else:
            self.send_key('f')
            if cancel and self.handle_claim_button():
                return False
        self.sleep(0.5)
        return True

    def get_stamina(self):
        boxes = self.wait_ocr(0.49, 0.01, 0.92, 0.10, log=True, raise_if_not_found=False,
                              match=[number_re, stamina_re])
        if len(boxes) == 0:
            return -1, -1
        current_box = find_boxes_by_name(boxes, stamina_re)[0]
        current = int(current_box.name.split('/')[0])
        back_up_box = find_boxes_by_name(boxes, number_re)[0]
        back_up = int(back_up_box.name)
        self.info_set('current_stamina', current)
        self.info_set('back_up_stamina', back_up)
        return current, back_up

    def ensure_stamina(self, min_stamina, max_stamina):
        current, back_up = self.get_stamina()
        if current >= max_stamina:
            return max_stamina, current + back_up - max_stamina, current - max_stamina, False
        elif current + back_up >= max_stamina:
            self.add_stamina(max_stamina - current)
            return max_stamina, current + back_up - max_stamina, 0, True
        elif current >= min_stamina:
            return min_stamina, current + back_up - min_stamina, current - min_stamina, False
        elif current + back_up >= min_stamina:
            self.add_stamina(min_stamina - current)
            return min_stamina, current + back_up - min_stamina, 0, True

    def add_stamina(self, to_add):
        self.click(0.83, 0.05, after_sleep=1)
        self.wait_ocr(0.41, 0.47, 0.45, 0.54, match=number_re, raise_if_not_found=True)
        self.click(0.7, 0.7, after_sleep=1)
        back_up = int(
            self.wait_ocr(0.6, 0.53, 0.66, 0.62, match=number_re, raise_if_not_found=True)[0].name)
        to_minus = back_up - to_add
        self.log_info(f'add_stamina, to_minus:{to_minus}, to_add:{to_add}, back_up:{back_up}')
        for _ in range(to_minus):
            self.click(0.24, 0.58, after_sleep=0.01)
        self.click_relative(0.69, 0.71, after_sleep=2)
        self.info_set('add_stamina', to_add)
        self.back(after_sleep=1)
        self.back(after_sleep=1)

    def send_key_and_wait_f(self, direction, raise_if_not_found, time_out, running=False, target_text=None,
                            cancel=True):
        if time_out <= 0:
            return
        start = time.time()
        if running:
            self.mouse_down(key='right')
        self.send_key_down(direction)
        f_found = self.wait_until(lambda: self.find_f_with_text(target_text=target_text), time_out=time_out,
                                  raise_if_not_found=False)
        if f_found:
            self.send_key('f')
            self.sleep(0.1)
        self.send_key_up(direction)
        if running:
            self.mouse_up(key='right')
        if not f_found:
            if raise_if_not_found:
                raise CannotFindException('cant find the f to enter')
            else:
                logger.warning(f"can't find the f to enter")
                return False

        remaining = time.time() - start

        if cancel and self.handle_claim_button():
            self.sleep(0.5)
            self.send_key_down(direction)
            if running:
                self.mouse_down(key='right')
            self.sleep(remaining + 0.2)
            if running:
                self.mouse_up(key='right')
            self.send_key_up(direction)
            return False
        return f_found

    def run_until(self, condiction, direction, time_out, raise_if_not_found=False, running=False):
        if time_out <= 0:
            return
        self.send_key_down(direction)
        if running:
            self.sleep(0.5)
            logger.debug(f'run_until condiction {condiction} direction {direction}')
            self.mouse_down(key='right')
        self.sleep(1)
        result = self.wait_until(condiction, time_out=time_out,
                                 raise_if_not_found=raise_if_not_found)
        self.send_key_up(direction)
        if running:
            self.mouse_up(key='right')
        return result

    def is_moving(self):
        return False

    def handle_claim_button(self):
        if self.wait_feature('claim_cancel_button_hcenter_vcenter', raise_if_not_found=False, horizontal_variance=0.05,
                             vertical_variance=0.1, time_out=1.5, threshold=0.8):
            self.sleep(0.5)
            self.send_key('esc')
            self.sleep(0.5)
            logger.info(f"found a claim reward")
            return True

    def find_echo(self, threshold=0.5) -> Box:
        """
        Main function to load ONNX model, perform inference, draw bounding boxes, and display the output image.

        Args:
            onnx_model (str): Path to the ONNX model.
            input_image (ndarray): Path to the input image.

        Returns:
            list: List of dictionaries containing detection information such as class_id, class_name, confidence, etc.
        """
        # Load the ONNX model
        boxes = og.my_app.yolo_detect(self.frame, label=12)
        ret = sorted(boxes, key=lambda detection: detection.confidence, reverse=True)
        if ret:
            return ret[0]

    def pick_echo(self):
        if self.find_f_with_text(target_text=self.absorb_echo_text()):
            self.send_key('f')
            if not self.handle_claim_button():
                return True

    def yolo_find_echo(self, use_color=True):
        if self.pick_echo():
            self.sleep(0.5)
            return True
        front_box = self.box_of_screen(0.35, 0.35, 0.65, 0.53, hcenter=True)
        color_threshold = 0.02
        for i in range(4):
            self.middle_click_relative(0.5, 0.5, down_time=0.2)
            self.sleep(0.4)
            echo = self.find_echo()
            if self.debug:
                self.draw_boxes('echo', echo)
            if echo and echo.center()[1] > self.height_of_screen(0.55):
                self.log_info(f'yolo found echo {echo}')
                if self.debug:
                    self.screenshot('echo_yolo_picked')
                return self.walk_to_box(self.find_echo, time_out=15, end_condition=self.pick_echo)
            if use_color:
                color_percent = self.calculate_color_percentage(echo_color, front_box)
                self.log_debug(f'pick_echo color_percent:{color_percent}')
                if color_percent > color_threshold:
                    if self.debug:
                        self.screenshot('echo_color_picked')
                    found = self.walk_find_echo(backward_time=0.5)
                    self.log_debug(f'found color_percent {color_percent} > {color_threshold}, walk now')
                    return found
            self.send_key('a', down_time=0.04)
            self.sleep(0.6)

        self.middle_click_relative(0.5, 0.5, down_time=0.2)
        picked = self.walk_find_echo()
        return picked

    def walk_find_echo(self, backward_time=1):
        if self.walk_until_f(time_out=4, backward_time=backward_time, target_text=self.absorb_echo_text(),
                             raise_if_not_found=False):  # find and pick echo
            logger.debug(f'farm echo found echo move forward walk_until_f to find echo')
            return True

    def incr_drop(self, dropped):
        if dropped:
            self.info['Echo Count'] = self.info.get('Echo Count', 0) + 1

    def should_check_monthly_card(self):
        if self.next_monthly_card_start > 0:
            if 0 < time.time() - self.next_monthly_card_start < 120:
                return True
        return False

    def sleep(self, timeout):
        return super().sleep(timeout - self.check_for_monthly_card())

    def wait_in_team_and_world(self, time_out=10, raise_if_not_found=True, esc=False):
        return self.wait_until(self.in_team_and_world, time_out=time_out, raise_if_not_found=raise_if_not_found,
                               post_action=lambda: self.back(after_sleep=2) if esc else None)

    def ensure_main(self, esc=True, time_out=30):
        self.info_set('current task', 'wait main')
        if not self.wait_until(lambda: self.is_main(esc=esc), time_out=time_out, raise_if_not_found=False):
            raise Exception('Please start in game world and in team!')
        self.info_set('current task', 'in main')

    def is_main(self, esc=True):
        if self.in_team_and_world():
            self._logged_in = True
            return True
        if self.handle_monthly_card():
            return True
        if self.wait_login():
            return True
        if esc:
            self.back(after_sleep=1.5)

    def wait_login(self):
        if not self._logged_in:
            if login := self.ocr(0.3, 0.3, 0.7, 0.7, match="登录"):
                self.click(login)
                self.log_info('点击登录按钮!')
                return False
            if self.find_one('login_account', threshold=0.7):
                self.wait_until(lambda: self.find_one('login_account', threshold=0.7) is None,
                                pre_action=lambda: self.click_relative(0.5, 0.9, after_sleep=3), time_out=30)
                self.wait_until(lambda: self.find_one('monthly_card', threshold=0.7) or self.in_team_and_world(),
                                pre_action=lambda: self.click_relative(0.5, 0.9, after_sleep=3), time_out=120)
                self.wait_until(lambda: self.in_team_and_world(),
                                post_action=lambda: self.click_relative(0.5, 0.9, after_sleep=3), time_out=5)
                self.log_info('Auto Login Success', notify=True)
                self._logged_in = True
                self.sleep(3)
                return True

    def in_team_and_world(self):
        return self.in_team()[
            0]  # and self.find_one(f'gray_book_button', threshold=0.7, canny_lower=50, canny_higher=150)

    def in_team(self):
        c1 = self.find_one('char_1_text',
                           threshold=0.75)
        c2 = self.find_one('char_2_text',
                           threshold=0.75)
        c3 = self.find_one('char_3_text',
                           threshold=0.75)
        arr = [c1, c2, c3]
        # logger.debug(f'in_team check {arr} time: {(time.time() - start):.3f}s')
        current = -1
        exist_count = 0
        for i in range(len(arr)):
            if arr[i] is None:
                if current == -1:
                    current = i
            else:
                exist_count += 1
        if exist_count == 2 or exist_count == 1:
            self._logged_in = True
            return True, current, exist_count + 1
        else:
            return False, -1, exist_count + 1

        # Function to check if a component forms a ring

    def handle_monthly_card(self):
        monthly_card = self.find_one('monthly_card', threshold=0.8)
        # self.screenshot('monthly_card1')
        if monthly_card is not None:
            # self.screenshot('monthly_card1')
            self.click_relative(0.50, 0.89)
            self.sleep(2)
            # self.screenshot('monthly_card2')
            self.click_relative(0.50, 0.89)
            self.sleep(2)
            self.wait_until(self.in_team_and_world, time_out=10,
                            post_action=lambda: self.click_relative(0.50, 0.89, after_sleep=1))
            # self.screenshot('monthly_card3')
            self.set_check_monthly_card(next_day=True)
        logger.debug(f'check_monthly_card {monthly_card}')
        return monthly_card is not None

    @property
    def game_lang(self):
        if '鸣潮' in self.hwnd_title:
            return 'zh_CN'
        elif 'Wuthering' in self.hwnd_title:
            return 'en_US'
        return 'unknown_lang'

    def teleport_to_boss(self, boss_name, use_custom=False, dead=False):
        self.zoom_map()
        pos = self.bosses_pos.get(boss_name)
        page = pos[0]
        index = pos[1]
        in_dungeon = pos[2]
        self.log_info(f'teleport to {boss_name} index {index} in_dungeon {in_dungeon}')
        self.sleep(1)
        self.openF2Book()

        gray_book_boss = self.wait_book()

        self.log_info(f'click {gray_book_boss}')
        self.click_box(gray_book_boss)
        self.sleep(2)

        if page == 1:  # weekly turtle
            logger.info('scroll down page 1')
            self.click_relative(1136 / 2560, 455 / 2160)
            self.sleep(1)
        elif page == 2:
            logger.info('scroll down page 2')
            self.click_relative(1136 / 2560, 550 / 2160)
            self.sleep(1)
        elif page == 3:
            logger.info('scroll down page 3')
            self.click_relative(1136 / 2560, 640 / 2160)
            self.sleep(1)

        x = 0.24
        y = 0.17
        step = (0.75 - y) / 6

        self.click_relative(x, y + step * index)
        self.sleep(1)
        self.log_info(f'index after scrolling down {index}')
        self.click_relative(0.89, 0.91)
        self.sleep(1)
        # 判断是否是角色死亡，需要传送复活状态
        if not dead:
            self.wait_click_travel(use_custom=use_custom)
        else:
            self.click_relative(0.92, 0.91)
            self.sleep(1)
            self.click_relative(0.68, 0.6)
        self.wait_in_team_and_world(time_out=120)
        self.sleep(1)

    def openF2Book(self, feature="gray_book_all_monsters"):
        self.log_info('click f2 to open the book')
        self.send_key_down('alt')
        self.sleep(0.05)
        self.click_relative(0.77, 0.05)
        self.send_key_up('alt')
        gray_book_boss = self.wait_book(feature)
        if not gray_book_boss:
            self.log_error("can't find gray_book_boss, make sure f2 is the hotkey for book", notify=True)
            raise Exception("can't find gray_book_boss, make sure f2 is the hotkey for book")
        return gray_book_boss

    def click_traval_button(self, use_custom=False):
        if feature := self.find_one(['fast_travel_custom', 'remove_custom', 'gray_teleport'], threshold=0.6):
            if feature.name == 'gray_teleport':
                if use_custom:
                    # if not self.wait_click_feature('custom_teleport_hcenter_vcenter', raise_if_not_found=False, time_out=3):
                    self.click_relative(0.5, 0.5, after_sleep=1)
                    # if self.wait_click_feature('gray_custom_way_point', raise_if_not_found=False, time_out=4):
                    #     self.sleep(1)
                    self.click_relative(0.68, 0.6, after_sleep=1)
                self.click_relative(0.74, 0.92, after_sleep=1)
                return True
            else:
                self.click_relative(0.74, 0.92, after_sleep=1)
                if self.wait_click_feature(['confirm_btn_hcenter_vcenter', 'confirm_btn_highlight_hcenter_vcenter'],
                                           relative_x=-1, raise_if_not_found=True,
                                           threshold=0.7,
                                           time_out=4):
                    self.wait_click_feature(['confirm_btn_hcenter_vcenter', 'confirm_btn_highlight_hcenter_vcenter'],
                                            relative_x=-1, raise_if_not_found=False,
                                            threshold=0.7,
                                            time_out=1)
                    return True
        elif btn := self.find_one('gray_teleport', threshold=0.7):
            return self.click_box(btn, relative_x=1)

    def wait_click_travel(self, use_custom=False):
        self.wait_until(lambda: self.click_traval_button(use_custom=use_custom), raise_if_not_found=True, time_out=10,
                        settle_time=1)

    def wait_book(self, feature="gray_book_all_monsters"):
        gray_book_boss = self.wait_until(
            lambda: self.find_one(feature, vertical_variance=0.8, horizontal_variance=0.05,
                                  threshold=0.3),
            time_out=3, settle_time=2)
        logger.info(f'found gray_book_boss {gray_book_boss}')
        # if self.debug:
        #     self.screenshot(feature)
        return gray_book_boss

    def check_main(self):
        if not self.in_team()[0]:
            self.click_relative(0, 0)
            self.send_key('esc')
            self.sleep(1)
            if not self.in_team()[0]:
                raise Exception('must be in game world and in teams')
        return True


echo_color = {
    'r': (200, 255),  # Red range
    'g': (150, 220),  # Green range
    'b': (130, 170)  # Blue range
}
