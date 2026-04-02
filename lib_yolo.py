        if COMMUNICATION_METHOD == "SOCKET" and g_conn is None:
            accept_connection()
            time.sleep(0.1)
            continue

        try:
            config.read(MAIN_SETTINGS_INI)
            if config.get('Vichop', 'vic_detect_request', fallback='false').lower() in ['true', '1', 'yes']:
                handle_vic_detection_request(vic_model, vic_input, capturer)
                config.set('Vichop', 'vic_detect_request', 'false')
                with open(MAIN_SETTINGS_INI, 'w') as f:
                    config.write(f)
                continue
        except:
            pass