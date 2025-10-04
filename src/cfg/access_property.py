from typing import Dict, List, Optional, Any, Callable, Tuple, Self

# from src.cfg import ASTNodeWrapper
import src.cfg as cfg


def resolve(self: 'cfg.ASTNodeWrapper', role: str, identification: dict = None, previous_action_data: 'cfg.ASTNodeWrapper' = None) -> 'cfg.ASTNodeWrapper | None':
    """
    Возвращает ASTNodeWrapper для ребёнка, соответствующего `role` или описанного в `identification`.
    Кэширует обёртки в self.children.

    Поддерживаемые варианты:
     - identification is None:
        читаем из self.children (если есть) или из self.value[role] (если value — dict).
     - identification provided:
        если в identification есть 'property_path' — выполняем путь (см. ниже).
        иначе — старая логика: origin/role_in_list/property.
    property_path: строка компонентов, разделённых '/', пробелы вокруг слэшей игнорируются.
        компоненты:
          '^'        — подняться к parent (wrapper)
          '[next]'   — перейти к следующему элементу в списке родителей (sibling next)
          '[N]'      — индекс N (число) при текущем value==list
          'name'     — доступ по ключу dict: current.value['name']
    Возвращает None если путь не может быть пройден.
    """
    # --- вспомогательные функции -----------------
    def make_wrapper_for(value, parent_wrapper):
        """Создаёт wrapper для value, задаёт parent, кеширует в parent.children если возможно."""
        if value is None:
            return None
        # value может уже быть ASTNodeWrapper — в таком случае просто используем её, но обновим parent если не задан
        if isinstance(value, cfg.ASTNodeWrapper):
            if value.parent is None and parent_wrapper is not None:
                value.parent = parent_wrapper
            return value

        w = cfg.ASTNodeWrapper(ast_node=value, parent=parent_wrapper)
        # кеширование: если parent.children — dict, попробуем подобрать ключ; если список — добавить при наличии
        if parent_wrapper is not None:
            pc = parent_wrapper.children
            # если parent.children пуст, и parent.value — dict, и value came from a key, we might not know key here
            # кеширование в основном делается там, где есть явный ключ; в остальных случаях — не кешируем.
            if isinstance(pc, dict):
                # no stable key known here — caller is expected to cache under specific key
                pass
            elif isinstance(pc, list):
                # если value уже представлен в parent.value (list), привяжем wrapper к соответствующей позиции
                try:
                    if isinstance(parent_wrapper.ast_node, list):
                        idx = parent_wrapper.ast_node.index(value)
                        # ensure list of wrappers length
                        while len(pc) < len(parent_wrapper.ast_node):
                            pc.append(None)
                        pc[idx] = w
                except Exception:
                    # best-effort: не критично
                    pass
        return w

    def ensure_children_structure():
        """Инициализирует self.children как dict или list, если ещё не инициализировано,
           в зависимости от self.value (dict->dict, list->list), иначе dict."""
        if self.children is not None:
            return
        if isinstance(self.ast_node, dict):
            self.children = {}
        elif isinstance(self.ast_node, list):
            self.children = [None] * len(self.ast_node)
        else:
            self.children = {}

    # --- основной код ----------------------------
    # 1) простая (без identification) логика: достать из кеша или из self.value по ключу
    if not identification:
        ensure_children_structure()
        # если children — dict, пробуем кеш и затем value lookup
        if isinstance(self.children, dict):
            child_wrapper = self.children.get(role)
            if child_wrapper is not None:
                return child_wrapper
            # попробуем взять из self.value если это dict
            if isinstance(self.ast_node, dict) and role in self.ast_node:
                val = self.ast_node[role]
                w = make_wrapper_for(val, self)
                # кешируем под ключом role
                self.children[role] = w
                return w
            # не нашли
            return None
        else:
            # children — list (редко для прямого доступа по role), попытаемся интерпретировать role как индекс '[N]' или '0'
            if isinstance(self.children, list):
                # try bracket index "[N]"
                role_str = role.strip()
                if role_str.startswith('[') and role_str.endswith(']'):
                    inner = role_str[1:-1].strip()
                    if inner.isdigit():
                        idx = int(inner)
                        if 0 <= idx < len(self.children):
                            w = self.children[idx]
                            if w is None:
                                # try to wrap underlying value
                                if isinstance(self.ast_node, list) and idx < len(self.ast_node):
                                    w = make_wrapper_for(self.ast_node[idx], self)
                                    self.children[idx] = w
                            return w
                # else: no sensible mapping
                return None

    # 2) identification-present logic
    # handle relative origin previous
    prop = identification.get('property') if identification else role
    origin = identification.get('origin') if identification else None
    role_in_list = identification.get('role_in_list') if identification else None
    prop_path = identification.get('property_path') if identification else None

    # if origin == 'previous' and property requested, delegate to previous_action_data
    if identification and origin == 'previous':
        if previous_action_data is None:
            # caller error — no previous action provided
            return None
        # use previous_action_data.get with property or property_path
        if prop_path:
            return previous_action_data.get(prop, {'property_path': prop_path}, None)
        else:
            return previous_action_data.get(prop)

    # if property_path present — traverse starting from self (wrapper)
    if prop_path:
        # normalize and split path: components separated by '/'
        comps = [c.strip() for c in prop_path.split('/') if c.strip() != ""]
        current: cfg.ASTNodeWrapper | None = self
        for comp in comps:
            if current is None:
                return None
            # upward move
            if comp == '^':
                if not previous_action_data:
                    # if going next from current, we should remember where started from (note this implementation limits us to at most one [next] in the chain).
                    previous_action_data = current
                current = current.parent
                continue
            # next sibling: require parent present and parent.children list-like
            if comp == '[next]':
                parent = current.parent
                if parent is None:
                    return None
                # ensure parent's children wrappers exist
                if parent.children is None:
                    # try to build parent.children from parent.value if it's a list
                    if isinstance(parent.ast_node, list):
                        parent.children = [None] * len(parent.ast_node)
                    else:
                        return None
                # find current index in parent's children (by wrapper identity or by matching value in parent.value)
                idx = None
                if isinstance(parent.children, list):
                    try:
                        idx = parent.children.index(current)
                    except ValueError:
                        # not present in cached wrappers: try to find by matching value in parent.value
                        if isinstance(parent.ast_node, list):
                            try:
                                idx = parent.ast_node.index(current.ast_node)
                            except ValueError:
                                idx = None
                else:
                    # parent's children is dict — try to find current among values
                    for k,v in (parent.children.items() if isinstance(parent.children, dict) else []):
                        if v is current:
                            # cannot determine order in dict => cannot do [next]
                            idx = None
                            break
                if idx is None:
                    return None
                nxt = idx + 1
                if not isinstance(parent.children, list) or nxt >= len(parent.children):
                    return None
                # ensure wrapper for next exists
                wnext = parent.children[nxt]
                if wnext is None:
                    # try to wrap underlying value
                    if isinstance(parent.ast_node, list) and nxt < len(parent.ast_node):
                        wnext = cfg.ASTNodeWrapper(ast_node=parent.ast_node[nxt], parent=parent)
                        parent.children[nxt] = wnext
                    else:
                        return None
                current = wnext
                continue
            # array index like [N]
            if comp.startswith('[') and comp.endswith(']'):
                inner = comp[1:-1].strip()
                if inner.isdigit():
                    idx = int(inner)
                    if isinstance(current.ast_node, list) and 0 <= idx < len(current.ast_node):
                        # ensure current.children is list and has wrapper
                        if current.children is None:
                            current.children = [None] * len(current.ast_node)
                        if isinstance(current.children, list):
                            if current.children[idx] is None:
                                current.children[idx] = cfg.ASTNodeWrapper(ast_node=current.ast_node[idx], parent=current)
                            current = current.children[idx]
                            continue
                        else:
                            # children not list => cannot index
                            return None
                # unsupported bracket content
                return None
            # normal property name: access dict key
            # if current.value is dict, get by key
            if isinstance(current.ast_node, dict):
                key = comp
                # try to use cached wrapper in current.children (dict) if available
                if current.children is None:
                    current.children = {}
                if isinstance(current.children, dict) and key in current.children and current.children[key] is not None:
                    current = current.children[key]
                    continue
                # otherwise get raw value and wrap
                raw = current.ast_node.get(key)
                if raw is None:
                    return None
                w = cfg.ASTNodeWrapper(ast_node=raw, parent=current)
                if isinstance(current.children, dict):
                    current.children[key] = w
                current = w
                continue
            # if we get here — cannot resolve component on current.value
            return None
        # finished traversal
        return current

    # 3) no property_path: handle role_in_list / property / origin parent
    # If role_in_list specified, we expect the property to be a list (either in self.children or in underlying value)
    if role_in_list:
        # if origin=='parent' then the list is located in parent; otherwise in self
        if origin == 'parent':
            parent = self.parent
            if parent is None:
                return None
            # list container could be parent.children (list) or parent.value[property]
            target_list = None
            if identification.get('property') and isinstance(parent.ast_node, dict):
                target_list = parent.ast_node.get(identification['property'])
            elif isinstance(parent.children, list):
                target_list = parent.children
            if not isinstance(target_list, list):
                return None
            # ensure parent.children is list of wrappers
            if parent.children is None or not isinstance(parent.children, list):
                # create wrapper list
                parent.children = [None] * len(target_list)
            if identification.get('role_in_list') == 'first_in_list':
                if len(target_list) == 0:
                    return None
                if parent.children[0] is None:
                    parent.children[0] = cfg.ASTNodeWrapper(ast_node=target_list[0], parent=parent)
                return parent.children[0]
            if identification.get('role_in_list') == 'next_in_list':
                # previous_action_data must be a wrapper present in that list
                if previous_action_data is None:
                    return None
                # find index of previous_action_data in parent.children or parent.value list
                idx = None
                if isinstance(parent.children, list):
                    try:
                        idx = parent.children.index(previous_action_data)
                    except ValueError:
                        # try to find by matching underlying value in parent.value list
                        if isinstance(parent.ast_node, list):
                            try:
                                idx = parent.ast_node.index(previous_action_data.ast_node)
                            except Exception:
                                idx = None
                if idx is None:
                    return None
                nx = idx + 1
                if nx >= len(parent.children):
                    return None
                if parent.children[nx] is None:
                    # create wrapper from parent.value if available
                    if isinstance(parent.ast_node, list) and nx < len(parent.ast_node):
                        parent.children[nx] = cfg.ASTNodeWrapper(ast_node=parent.ast_node[nx], parent=parent)
                    else:
                        return None
                return parent.children[nx]
            # unknown role_in_list
            return None
        else:
            # origin not parent => look in self
            target_list = None
            if identification.get('property') and isinstance(self.ast_node, dict):
                target_list = self.ast_node.get(identification['property'])
            elif isinstance(self.children, list):
                target_list = self.children
            if not isinstance(target_list, list):
                return None
            # ensure self.children is list of wrappers
            if self.children is None or not isinstance(self.children, list):
                self.children = [None] * len(target_list)
            if role_in_list == 'first_in_list':
                if len(target_list) == 0:
                    return None
                if self.children[0] is None:
                    # wrap underlying value if exists
                    if isinstance(self.ast_node, list) and 0 < len(self.ast_node):
                        self.children[0] = cfg.ASTNodeWrapper(ast_node=self.ast_node[0], parent=self)
                    else:
                        # if target_list already contains wrappers, use them
                        if isinstance(target_list[0], cfg.ASTNodeWrapper):
                            self.children[0] = target_list[0]
                        else:
                            self.children[0] = cfg.ASTNodeWrapper(ast_node=target_list[0], parent=self)
                return self.children[0]
            if role_in_list == 'next_in_list':
                if previous_action_data is None:
                    return None
                # find index of previous_action_data
                try:
                    idx = self.children.index(previous_action_data)
                except Exception:
                    # try locate in underlying list
                    idx = None
                    if isinstance(self.ast_node, list):
                        try:
                            idx = self.ast_node.index(previous_action_data.ast_node)
                        except Exception:
                            idx = None
                if idx is None:
                    return None
                nx = idx + 1
                if nx >= len(self.children):
                    return None
                if self.children[nx] is None:
                    if isinstance(self.ast_node, list) and nx < len(self.ast_node):
                        self.children[nx] = cfg.ASTNodeWrapper(ast_node=self.ast_node[nx], parent=self)
                    else:
                        return None
                return self.children[nx]
            return None

    # 4) fallback: try to use identification['property'] direct lookup in self.value (dict)
    if identification and 'property' in identification:
        prop = identification['property']
        # if origin == 'parent', lookup in parent
        if identification.get('origin') == 'parent':
            parent = self.parent
            if parent is None:
                return None
            # ensure parent's children is dict
            if parent.children is None:
                parent.children = {}
            if isinstance(parent.children, dict) and prop in parent.children and parent.children[prop] is not None:
                return parent.children[prop]
            # otherwise try to wrap parent's underlying value[prop]
            if isinstance(parent.ast_node, dict) and prop in parent.ast_node:
                w = cfg.ASTNodeWrapper(ast_node=parent.ast_node[prop], parent=parent)
                if isinstance(parent.children, dict):
                    parent.children[prop] = w
                return w
            return None
        else:
            # lookup in self.value
            if self.children is None:
                self.children = {}
            if isinstance(self.children, dict) and prop in self.children and self.children[prop] is not None:
                return self.children[prop]
            if isinstance(self.ast_node, dict) and prop in self.ast_node:
                w = cfg.ASTNodeWrapper(ast_node=self.ast_node[prop], parent=self)
                if isinstance(self.children, dict):
                    self.children[prop] = w
                return w
            return None

    # if nothing matched — return None
    return None
