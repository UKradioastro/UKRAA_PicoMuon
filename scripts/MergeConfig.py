#!/usr/bin/env python3

import argparse
import configparser
import os
import re
import tempfile


SECTION_PATTERN = re.compile(r'^\s*\[([^]]+)\]\s*(?:[;#].*)?$')


def _load_parser(path):
    parser = configparser.ConfigParser(interpolation=None)
    with open(path, mode='r', encoding='UTF-8-sig') as config_file:
        parser.read_file(config_file)
    return parser


def _find_section_end(lines, section_name):
    section_start = None
    for line_index, line in enumerate(lines):
        section_match = SECTION_PATTERN.match(line)
        if not section_match:
            continue

        if section_start is not None:
            return line_index
        if section_match.group(1) == section_name:
            section_start = line_index

    return len(lines) if section_start is not None else None


def merge_missing_options(template_path, config_path):
    template = _load_parser(template_path)
    config = _load_parser(config_path)

    with open(config_path, mode='r', encoding='UTF-8-sig') as config_file:
        lines = config_file.readlines()

    additions = []
    for section_name in template.sections():
        missing_options = [
            option_name
            for option_name in template.options(section_name)
            if not config.has_option(section_name, option_name)
        ]
        if not missing_options:
            continue

        section_end = _find_section_end(lines, section_name)
        option_lines = [
            f'{option_name} = {template.get(section_name, option_name, raw=True)}\n'
            for option_name in missing_options
        ]

        if section_end is None:
            if lines and lines[-1].strip():
                lines.append('\n')
            lines.extend([f'[{section_name}]\n', *option_lines])
        else:
            lines[section_end:section_end] = [*option_lines, '\n']

        additions.extend(
            f'{section_name}.{option_name}' for option_name in missing_options)
        config = _load_parser_from_lines(lines)

    if additions:
        _replace_config(config_path, lines)

    return additions


def set_config_values(config_path, section_name, option_values):
    _load_parser(config_path)
    with open(config_path, mode='r', encoding='UTF-8-sig') as config_file:
        lines = config_file.readlines()

    section_start = None
    for line_index, line in enumerate(lines):
        section_match = SECTION_PATTERN.match(line)
        if section_match and section_match.group(1) == section_name:
            section_start = line_index
            break

    changed = False
    missing_options = []
    if section_start is None:
        if lines and lines[-1].strip():
            lines.append('\n')
        lines.append(f'[{section_name}]\n')
        missing_options = list(option_values.items())
    else:
        section_end = _find_section_end(lines, section_name)
        for option_name, value in option_values.items():
            option_pattern = re.compile(
                rf'^\s*{re.escape(option_name)}\s*[:=]')
            option_index = next(
                (line_index for line_index in range(section_start + 1, section_end)
                 if option_pattern.match(lines[line_index])),
                None)
            replacement = f'{option_name} = {value}\n'
            if option_index is None:
                missing_options.append((option_name, value))
            elif lines[option_index] != replacement:
                lines[option_index] = replacement
                changed = True

        if missing_options:
            insert_at = section_end
            while insert_at > section_start + 1 and not lines[insert_at - 1].strip():
                insert_at -= 1
            lines[insert_at:insert_at] = [
                f'{option_name} = {value}\n'
                for option_name, value in missing_options]
            changed = True

    if section_start is None:
        lines.extend(
            f'{option_name} = {value}\n'
            for option_name, value in missing_options)
        changed = True

    if changed:
        _replace_config(config_path, lines)

    return changed


def _load_parser_from_lines(lines):
    parser = configparser.ConfigParser(interpolation=None)
    parser.read_string(''.join(lines))
    return parser


def _replace_config(config_path, lines):
    config_stat = os.stat(config_path)
    config_directory = os.path.dirname(os.path.abspath(config_path))
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
                mode='w', encoding='UTF-8', newline='',
                dir=config_directory, delete=False) as temporary_file:
            temporary_path = temporary_file.name
            temporary_file.writelines(lines)

        os.chmod(temporary_path, config_stat.st_mode)
        if hasattr(os, 'chown'):
            os.chown(temporary_path, config_stat.st_uid, config_stat.st_gid)
        os.replace(temporary_path, config_path)
    finally:
        if temporary_path and os.path.exists(temporary_path):
            os.unlink(temporary_path)


def main():
    argument_parser = argparse.ArgumentParser(
        description='Add missing template options to an existing INI file.')
    argument_parser.add_argument('--set-web-url')
    argument_parser.add_argument('template_path')
    argument_parser.add_argument('config_path')
    arguments = argument_parser.parse_args()

    if arguments.set_web_url:
        set_config_values(arguments.config_path, 'web', {'url': arguments.set_web_url})
        print('Set fresh-install web URL: ' + arguments.set_web_url)
        return

    additions = merge_missing_options(
        arguments.template_path, arguments.config_path)
    if additions:
        print('Added configuration defaults: ' + ', '.join(additions))
    else:
        print('Configuration already contains all current options.')


if __name__ == '__main__':
    main()
