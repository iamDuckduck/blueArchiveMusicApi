package com.ba.bluearchivemusicapi.entities;

import jakarta.persistence.*;
import lombok.*;
import org.hibernate.annotations.BatchSize;
import org.springframework.data.annotation.CreatedDate;
import org.springframework.data.annotation.LastModifiedDate;
import org.springframework.data.jpa.domain.support.AuditingEntityListener;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;
import java.util.stream.Collectors;

@Setter
@Getter
@AllArgsConstructor
@NoArgsConstructor
@Entity
@Builder
@EntityListeners(AuditingEntityListener.class)
@Table(name = "song", uniqueConstraints = @UniqueConstraint(
        name = "uq_song_import_identity", columnNames = {"album_id", "import_source", "source_track_id"}))
public class Song {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "title")
    private String title;

    @Column(name = "image_path")
    private String imagePath;

    @Column(name = "audio_path")
    private String audioPath;

    @Column(name = "description", columnDefinition = "TEXT")
    private String description;

    @Column(name = "play_count")
    private Long playCount;

    @Column(name = "disc_number")
    private Integer discNumber;

    @Column(name = "track_number")
    private Integer trackNumber;

    @Column(name = "import_source", length = 64)
    private String importSource;

    @Column(name = "source_track_id", length = 255)
    private String sourceTrackId;

    @Column(name = "music_kind", length = 32)
    private String musicKind;

    @CreatedDate
    @Column(name = "created_date")
    private LocalDate createdDate;

    @LastModifiedDate
    @Column(name = "updated_date")
    private LocalDate updatedDate;

    @ManyToOne
    @JoinColumn(name = "album_id")
    private Album album;

    @OneToMany(mappedBy = "song", cascade = CascadeType.ALL, orphanRemoval = true)
    @BatchSize(size = 50)
    @Builder.Default
    private List<SongArtist> songArtists = new ArrayList<>();

    // ──── Helper methods ────

    public List<Artist> getArtists() {
        return songArtists.stream()
                .filter(sa -> sa.getType() == SongArtistType.ARTIST)
                .map(SongArtist::getArtist)
                .collect(Collectors.toList());
    }

    public List<Artist> getComposers() {
        return songArtists.stream()
                .filter(sa -> sa.getType() == SongArtistType.COMPOSER)
                .map(SongArtist::getArtist)
                .collect(Collectors.toList());
    }

    public void addArtist(Artist artist, SongArtistType type) {
        SongArtist sa = SongArtist.builder()
                .song(this)
                .artist(artist)
                .type(type)
                .build();
        songArtists.add(sa);
    }
}
