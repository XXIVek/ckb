#!/usr/bin/env python3
"""Модуль отслеживания изменений объектов конфигурации.

Поддержка полного цикла: загрузка → редактирование → экспорт.
"""


def _get_config_db_connection():
    """Получить соединение с БД configurations."""
    import psycopg2
    return psycopg2.connect(
        host='localhost', port=5432, dbname='configurations',
        user='postgres', password='Sta090860'
    )


def mark_object_modified(config_id: int, target_type: str, target_name: str, modified: bool = True) -> dict:
    """Отметить объект конфигурации как изменённый/неизменённый.

    Args:
        config_id: ID конфигурации
        target_type: тип объекта (catalog, document, register_info и т.д.)
        target_name: имя объекта
        modified: True = помечен как изменённый, False = снят с отметки

    Returns:
        Словарь с результатом
    """
    conn = _get_config_db_connection()
    try:
        cur = conn.cursor()
        
        safe_type = target_type.replace("'", "''")
        safe_name = target_name.replace("'", "''")
        
        sql = f"""
            UPDATE configuration_objects 
            SET modified = {modified}, updated_at = NOW()
            WHERE configuration_id = {config_id} 
              AND type = '{safe_type}' 
              AND name = '{safe_name}'
        """
        
        cur.execute(sql)
        affected = cur.rowcount
        
        conn.commit()
        cur.close()
        
        if affected > 0:
            status = "изменён" if modified else "не изменён"
            return {
                'success': True,
                'config_id': config_id,
                'target_type': target_type,
                'target_name': target_name,
                'status': status
            }
        else:
            return {
                'success': False,
                'error': f'Объект не найден: {target_type}/{target_name}'
            }
    
    except Exception as e:
        conn.rollback()
        return {'success': False, 'error': str(e)}
    finally:
        conn.close()


def get_modified_objects(config_id: int) -> list:
    """Получить все изменённые объекты конфигурации.

    Args:
        config_id: ID конфигурации

    Returns:
        Список изменённых объектов
    """
    conn = _get_config_db_connection()
    try:
        cur = conn.cursor()
        
        sql = f"""
            SELECT id, type, name, description, file_relative_path, 
                   updated_at, LENGTH(original_xml) as xml_size
            FROM configuration_objects 
            WHERE configuration_id = {config_id} 
              AND modified = TRUE
            ORDER BY updated_at DESC
        """
        
        cur.execute(sql)
        rows = cur.fetchall()
        
        result = []
        for row in rows:
            result.append({
                'id': row[0],
                'type': row[1],
                'name': row[2],
                'description': row[3],
                'file_relative_path': row[4],
                'updated_at': str(row[5]) if row[5] else None,
                'xml_size': row[6]
            })
        
        cur.close()
        return result
    
    except Exception as e:
        return [{'error': str(e)}]
    finally:
        conn.close()


def clear_modified_flag(config_id: int, target_type: str, target_name: str) -> dict:
    """Снять отметку об изменении с объекта.

    Args:
        config_id: ID конфигурации
        target_type: тип объекта
        target_name: имя объекта

    Returns:
        Словарь с результатом
    """
    return mark_object_modified(config_id, target_type, target_name, modified=False)


def count_modified_objects(config_id: int) -> dict:
    """Подсчитать количество изменённых объектов.

    Args:
        config_id: ID конфигурации

    Returns:
        Словарь с подсчётом
    """
    conn = _get_config_db_connection()
    try:
        cur = conn.cursor()
        
        sql = f"""
            SELECT type, COUNT(*) as cnt 
            FROM configuration_objects 
            WHERE configuration_id = {config_id} 
              AND modified = TRUE
            GROUP BY type
            ORDER BY cnt DESC
        """
        
        cur.execute(sql)
        rows = cur.fetchall()
        
        total = 0
        by_type = []
        for row in rows:
            by_type.append({'type': row[0], 'count': row[1]})
            total += row[1]
        
        cur.close()
        return {
            'total': total,
            'by_type': by_type
        }
    
    except Exception as e:
        return {'error': str(e)}
    finally:
        conn.close()
