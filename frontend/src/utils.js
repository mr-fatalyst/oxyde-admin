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
