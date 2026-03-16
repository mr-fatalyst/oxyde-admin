/**
 * Find the primary key value in a record using schema field definitions.
 * @param {Object} record - The data record.
 * @param {Array} fields - Field definitions with `isPk` and `name`.
 * @returns {*} The PK value or null.
 */
export function findPk(record, fields) {
    const pkField = fields.find((f) => f.isPk);
    return pkField ? record[pkField.name] : null;
}

/**
 * Serialize a Date to a string suitable for the API.
 * - date-only fields → local YYYY-MM-DD (preserves what the user picked)
 * - datetime fields  → full ISO 8601 UTC string
 */
export function serializeDate(val, format) {
    if (format === 'date') {
        const y = val.getFullYear();
        const m = String(val.getMonth() + 1).padStart(2, '0');
        const d = String(val.getDate()).padStart(2, '0');
        return `${y}-${m}-${d}`;
    }
    return val.toISOString();
}

// --- Schema helpers (shared between ModelDetail and ModelList) ---

export function resolveType(prop) {
    if (prop.type) return prop.type;
    if (prop.anyOf) {
        const nonNull = prop.anyOf.find((t) => t.type && t.type !== 'null');
        if (nonNull) return nonNull.type;
    }
    return 'string';
}

export function hasRef(prop) {
    if (prop.$ref) return true;
    if (prop.anyOf) return prop.anyOf.some((t) => t.$ref);
    return false;
}

export function resolveFormat(prop) {
    if (prop.format) return prop.format;
    if (prop.anyOf) {
        const nonNull = prop.anyOf.find((t) => t.format);
        if (nonNull) return nonNull.format;
    }
    return null;
}

export function resolveEnum(prop) {
    if (prop.enum) return prop.enum;
    if (prop.anyOf) {
        const withEnum = prop.anyOf.find((t) => t.enum);
        if (withEnum) return withEnum.enum;
    }
    return null;
}

export function extractFkMap(schemaData) {
    const map = {};
    const props = schemaData.properties || {};
    for (const [, prop] of Object.entries(props)) {
        if (!hasRef(prop)) continue;
        const fk = prop['x-db-foreign-key'];
        const col = prop['x-db-column'];
        if (fk && col) {
            map[col] = fk;
        }
    }
    return map;
}

export function componentType(field) {
    if (field.m2m) return 'multiselect';
    if (field.fk) return 'select';
    if (field.enum) return 'enum';
    if (field.type === 'boolean') return 'boolean';
    if (field.type === 'integer' || field.type === 'number') return 'number';
    if (field.format === 'date-time') return 'datetime';
    if (field.format === 'date') return 'date';
    if (field.type === 'string' && !field.maxLength && (!field.dbType || field.dbType.toUpperCase() === 'TEXT')) return 'textarea';
    return 'text';
}
