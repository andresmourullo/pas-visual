const express = require('express');
const fs = require('fs');
const csv = require('csv-parser');
const path = require('path');
const app = express();
const PORT = 3000;

// Servir archivos estáticos (la web en la carpeta public)
app.use(express.static('public'));

// Variable para guardar los datos en memoria
let pasData = [];

// Función para cargar el CSV al iniciar
function loadCSV() {
    const csvPath = path.join(__dirname, 'pas.csv');
    
    if (!fs.existsSync(csvPath)) {
        console.error("❌ ERROR: No se encuentra el archivo 'pas.csv'. Asegúrate de ponerlo en la misma carpeta que server.js");
        return;
    }

    fs.createReadStream(csvPath)
        .pipe(csv())
        .on('data', (row) => {
            // Limpieza básica de datos mientras leemos
            pasData.push(row);
        })
        .on('end', () => {
            console.log(`✅ CSV Cargado correctamente: ${pasData.length} registros encontrados.`);
        });
}

// Endpoint API: La web pedirá los datos aquí
app.get('/api/pas', (req, res) => {
    res.json(pasData);
});

// Iniciar servidor y cargar datos
app.listen(PORT, () => {
    console.log(`🚀 Servidor funcionando en http://localhost:${PORT}`);
    loadCSV();
});