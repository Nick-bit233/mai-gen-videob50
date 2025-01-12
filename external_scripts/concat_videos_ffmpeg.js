const concat = require('ffmpeg-concat')
const fs = require('fs')
const path = require('path')

// 解析命令行参数
const args = process.argv.slice(2)
const argv = require('minimist')(args, {
  string: ['output', 'videos', 'transition-name'],
  number: ['transition-duration'],
  alias: {
    o: 'output',
    v: 'videos',
    t: 'transition-name',
    d: 'transition-duration'
  },
  default: {
    'transition-name': 'crosswarp',
    'transition-duration': 500
  }
})

// 显示帮助信息
if (argv.help || argv.h) {
  console.log(`
Usage: node concat_videos_ffmpeg.js [options]

Options:
  -o, --output              输出视频路径 (必需)
  -v, --videos             视频列表文件路径 (必需)
  -t, --transition-name    转场效果名称 (默认: crosswarp)
  -d, --transition-duration 转场时长(ms) (默认: 500)
  -h, --help              显示帮助信息

Example:
  node concat_videos_ffmpeg.js -o ./output.mp4 -v ./video_list.txt -t crosswarp -d 500
  `)
  process.exit(0)
}

// 检查必需参数
if (!argv.output || !argv.videos) {
  console.error('Error: Missing required arguments (output and videos)')
  process.exit(1)
}

async function concatenateVideos(output, videoListFile, transitionName, transitionDuration) {
    try {
        const fileContent = fs.readFileSync(videoListFile, 'utf8')
        console.log('Raw file content:', fileContent)

        const videoList = fileContent
            .split('\n')
            .filter(line => line.trim())
            .map(line => {
                console.log('Processing line:', line)
                const match = line.trim().match(/^file\s+'\.\/(.+)'$/)
                console.log('Match result:', match)
                const result = match ? match[1] : line.trim()
                console.log('Processed result:', result)
                return result
            })
            .filter(path => path)

        console.log('Final videoList:', videoList)

        if (videoList.length === 0) {
            throw new Error('No videos found in the list file')
        }

        console.log('Processing videos:', videoList)

        // 执行视频拼接
        await concat({
            output: output,
            videos: videoList,
            transition: {
                name: transitionName,
                duration: transitionDuration
            }
        })

        console.log('Video concatenation completed successfully!')
  } catch (error) {
        console.error('Error during video concatenation:', error)
        process.exit(1)
  }
}

// 执行主函数
concatenateVideos(
  argv.output,
  argv.videos,
  argv['transition-name'],
  argv['transition-duration']
).catch(console.error)